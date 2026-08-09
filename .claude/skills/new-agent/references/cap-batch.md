# cap-batch — Templates for batch-runner-builder subagent

**Tier: T2 — Runtime-adjacent.** Claude API has a provider-side batch endpoint (NATIVE); other runtimes use client-side concurrency (ASSEMBLABLE).

## Agnostic contract

A dataset of independent inputs must be processable through the agent with bounded concurrency, per-item failure isolation (one failure must not abort the run), per-item latency and error capture, and results written durably in a resumable, order-independent format keyed by a stable per-item identifier. The "keyed by stable identifier, order-independent" clause is the one provider batch APIs enforce and naive implementations miss.

| Runtime | Support | Notes |
|---|---|---|
| Claude API | NATIVE | Message Batches API: `client.messages.batches.create(requests=[{custom_id, params}])` → poll `processing_status` → stream `results()`. 50% cost, up to 100k requests / 256 MB, most complete within 1 hour. **Results arrive in any order — key by `custom_id`, never by position.** Combines with prompt caching for a shared system prefix. Preferred over client-side concurrency for non-latency-sensitive work |
| Google ADK | ASSEMBLABLE | Client-side concurrency; Vertex Batch API exists for embeddings; Agent Platform batch support was forthcoming as of research date |
| LangGraph | ASSEMBLABLE | `graph.abatch()` / `RunnableConfig(max_concurrency=N)`; durability via checkpointer |
| Vercel AI SDK | ASSEMBLABLE | No batch primitive; `Promise.all` with concurrency limiter, or Workflow SDK for durable fan-out |

> **Spec note:** The `BatchRunner` here implements the client-side semaphore pattern with incremental append (`write_result` appends per item, not at end) and resume (`completed_ids()` skips already-written items on restart). This is the correct fallback pattern for any runtime. For Claude, **prefer the Message Batches API route**: 50% cost, up to 100k requests / 256 MB per batch, most complete within 1 hour. Minimal scaffold:
> ```python
> import anthropic
> client = anthropic.Anthropic()
> batch = client.messages.batches.create(
>     requests=[
>         {"custom_id": item["id"], "params": {"model": "claude-sonnet-4-5", "max_tokens": 1024, "messages": [{"role": "user", "content": item["query"]}]}}
>         for item in items
>     ]
> )
> # Poll until batch.processing_status == "ended"
> for result in client.messages.batches.results(batch.id):
>     # result.custom_id maps back to item["id"] — results arrive in any order
>     process(result.custom_id, result.result)
> ```
> Combines with prompt caching on a shared system prefix. Do not use for latency-sensitive workloads (batch API adds ~1h latency by design).

## File: {OUTPUT_DIR}/batch_runner.py

```python
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import time
import uuid
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class BatchRunner:
    """Process a JSONL input file through the agent with concurrency control.

    Each line of the input file must be a JSON object with at minimum a "query" key.
    Results are written as JSONL with the original item plus agent output and timing.

    Usage:
        runner = BatchRunner("data/queries.jsonl", "data/results.jsonl", concurrency=10)
        asyncio.run(runner.run_all())

    Or via CLI:
        uv run python -m {AGENT_NAME}.batch_runner --input data/queries.jsonl \\
            --output data/results.jsonl --concurrency 10
    """

    def __init__(
        self,
        input_path: str,
        output_path: str,
        concurrency: int = 10,
        resume: bool = True,
    ) -> None:
        self.input_path = Path(input_path)
        self.output_path = Path(output_path)
        self.concurrency = concurrency
        self.resume = resume
        self._semaphore = asyncio.Semaphore(concurrency)
        # Serializes appends from concurrent workers so interleaved writes
        # cannot produce a torn JSONL line.
        self._write_lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Dataset loading
    # ------------------------------------------------------------------

    def load_items(self) -> list[dict[str, Any]]:
        """Read JSONL input file and return a list of item dicts."""
        if not self.input_path.exists():
            raise FileNotFoundError(f"Input file not found: {self.input_path}")

        items: list[dict[str, Any]] = []
        with self.input_path.open() as fh:
            for line_no, line in enumerate(fh, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    item = json.loads(line)
                    if "query" not in item:
                        logger.warning("Line %d missing 'query' key — skipping", line_no)
                        continue
                    items.append(item)
                except json.JSONDecodeError as exc:
                    logger.warning("Line %d JSON parse error: %s — skipping", line_no, exc)

        logger.info("Loaded %d items from %s", len(items), self.input_path)
        return items

    # ------------------------------------------------------------------
    # Single-item execution
    # ------------------------------------------------------------------

    async def run_item(self, item: dict[str, Any]) -> dict[str, Any]:
        """Call the agent for one item and return result dict with timing.

        Errors are captured and surfaced in the result rather than raised,
        so a single failure doesn't abort the batch.
        """
        from {AGENT_NAME}.main import AgentRunner  # noqa: PLC0415

        session_id = item.get("session_id") or str(uuid.uuid4())
        query = item["query"]
        start = time.monotonic()

        async with self._semaphore:
            try:
                runner = AgentRunner(session_id=session_id)
                response = await runner.run(query)

                result = {
                    **item,
                    "session_id": session_id,
                    "response": response.model_dump(),
                    "latency_s": round(time.monotonic() - start, 3),
                    "error": None,
                }
            except Exception as exc:  # noqa: BLE001
                logger.error("Agent failed for query %r: %s", query[:80], exc)
                result = {
                    **item,
                    "session_id": session_id,
                    "response": None,
                    "latency_s": round(time.monotonic() - start, 3),
                    "error": str(exc),
                }

        # Persist outside the semaphore — the write must not consume a
        # concurrency slot that an in-flight API call could be using.
        await self.write_result(result)
        return result

    # ------------------------------------------------------------------
    # Orchestration
    # ------------------------------------------------------------------

    async def run_all(self) -> list[dict[str, Any]]:
        """Process all items concurrently and write results to output JSONL.

        Returns the list of result dicts (also written to disk).
        """
        try:
            from tqdm.asyncio import tqdm_asyncio as tqdm_gather  # type: ignore[import]

            use_tqdm = True
        except ImportError:
            use_tqdm = False

        items = self.load_items()

        if not items:
            logger.warning("No items to process")
            return []

        # Resume: skip anything already durably written by a previous run.
        already_done = self.completed_ids() if self.resume else set()
        if already_done:
            items = [i for i in items if str(i.get("id")) not in already_done]
            logger.info(
                "Resuming: %d already complete, %d remaining",
                len(already_done),
                len(items),
            )
            if not items:
                logger.info("Nothing left to process")
                return []

        logger.info(
            "Starting batch: %d items, concurrency=%d, output=%s",
            len(items),
            self.concurrency,
            self.output_path,
        )
        batch_start = time.monotonic()

        tasks = [self.run_item(item) for item in items]

        if use_tqdm:
            results = await tqdm_gather.gather(*tasks, desc="{AGENT_NAME} batch")
        else:
            results = await asyncio.gather(*tasks)

        elapsed = time.monotonic() - batch_start
        # Results were already appended by run_item as each completed.

        # Summary stats
        errors = sum(1 for r in results if r["error"])
        latencies = [r["latency_s"] for r in results if r["error"] is None]
        avg_latency = sum(latencies) / len(latencies) if latencies else 0.0

        logger.info(
            "Batch complete: %d/%d succeeded in %.1fs (avg latency %.2fs per item)",
            len(results) - errors,
            len(results),
            elapsed,
            avg_latency,
        )

        if errors > 0:
            logger.warning("%d item(s) failed — check 'error' field in output", errors)

        return list(results)

    # ------------------------------------------------------------------
    # Output
    # ------------------------------------------------------------------

    async def write_result(self, result: dict[str, Any]) -> None:
        """Append a single result to the output JSONL, flushed to disk.

        Appended per item rather than written once at the end: a batch that
        crashes at item 9,999 of 10,000 must not lose the 9,998 completed calls
        that were already paid for.
        """
        self.output_path.parent.mkdir(parents=True, exist_ok=True)

        async with self._write_lock:
            with self.output_path.open("a") as fh:
                fh.write(json.dumps(result, default=str) + "\n")
                fh.flush()

    def completed_ids(self) -> set[str]:
        """IDs already present in the output file, for resuming an interrupted run.

        A truncated final line (the crash itself) is skipped rather than fatal.
        """
        if not self.output_path.exists():
            return set()

        done: set[str] = set()
        with self.output_path.open() as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    done.add(str(json.loads(line)["id"]))
                except (json.JSONDecodeError, KeyError):
                    continue
        return done


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    parser = argparse.ArgumentParser(
        description="Run {AGENT_NAME} over a JSONL input file",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Path to JSONL input file (each line: {\"query\": \"...\", ...})",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Path to write JSONL results",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=10,
        help="Maximum parallel agent calls",
    )
    args = parser.parse_args()

    runner = BatchRunner(
        input_path=args.input,
        output_path=args.output,
        concurrency=args.concurrency,
    )
    asyncio.run(runner.run_all())


if __name__ == "__main__":
    main()
```
