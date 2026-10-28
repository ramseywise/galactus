# llm_kit — a 60-minute Anthropic starter

One file, one test file, `anthropic` and the stdlib. Copy it into an empty
directory and you have working, honest Claude calls in under a minute.

It exists for the case where you have 60 minutes, no scaffold, and a blank
`main.py` — a take-home, a spike, a demo the morning it is due.

---

## This kit does not ship into rendered projects

**Intentional.** `template/llm_kit/` has no `_tasks` entry in `copier.yaml`, so
`copier copy` never renders it into a generated project. This is not an
omission — it is the delivery decision.

A kit that only appears *after* a 15–20 minute copier render solves nothing for
someone who has 60 minutes total. So it stays a repo-only asset you `git clone`
or copy directly. If a future need arises to also render it into projects, that
is a `_tasks` entry plus a `copier.yaml` question — a separate change, not a
bug fix.

It is also plain Python, not Jinja, for the same reason: it must be
copy-pasteable into a context that has never heard of copier.

---

## Quickstart (60 seconds)

```bash
cp -r template/llm_kit ~/my-spike && cd ~/my-spike
export ANTHROPIC_API_KEY=sk-ant-...
uv run --group dev pytest -q     # 5 tests, offline, no key needed
uv run python llm_kit.py         # smoke check, costs one call
```

Then in your own code:

```python
from llm_kit import call, text_of, cost_of, guard_tokens

guard_tokens(prompt, limit=50_000)          # fail before you spend
resp = call(prompt, system="You are terse.")
print(text_of(resp))                         # loud on truncation / empty
print(f"${cost_of(resp):.4f}")
```

Structured output, when you want objects instead of prose:

```python
from pydantic import BaseModel
from llm_kit import parsed

class Ticket(BaseModel):
    title: str
    severity: int

ticket = parsed("Summarize this incident: ...", Ticket)
```

`pydantic` arrives transitively with `anthropic`, so this adds no dependency.

### Running the tests

From inside the kit directory (the form that works on a clean checkout):

```bash
uv run --group dev pytest -q
```

From the template repo root, point `uv` at the kit's project file — the repo
root has no Python project of its own, so a bare `uv run pytest` will not find
an interpreter:

```bash
uv run --project template/llm_kit --group dev pytest template/llm_kit/ -v
```

Both run with `ANTHROPIC_API_KEY` unset and make no network calls.

---

## The 60-minute clock

| Minutes | Phase | What you are doing |
|---|---|---|
| 0–10 | **Triage** | Read the prompt twice. Write down what "done" is. Pick the *one* thing that must work. Copy the kit, run the tests, confirm one live call succeeds. Do not design. |
| 10–40 | **Execution** | Build the one thing, end to end, ugly. Hardcode what you can defend later. `text_of` and `cost_of` keep you honest while you go — if a call truncates, you find out now, not in the demo. |
| 40–50 | **Hardening** | Make the failure paths visible. Guard the token budget. Add the one test that would have caught the bug you actually hit. Not three tests — the one. |
| 50–60 | **Docs** | Fill in the trade-off template below. This is scored more often than the code is. Do not skip it to squeeze in one more feature. |

The clock's real content is the 40-minute mark: **stop adding features there
even if it feels unfinished.** An honest, documented, narrow thing beats a broad
thing with no story about its limits.

---

## Trade-off template — fill this in

Copy this into your submission's README. Reviewers read it first.

```markdown
### What I chose

- **Scope**: I built ___. I did not build ___ because ___.
- **Model**: `claude-opus-5` at `max_tokens=___` because ___.
- **Failure handling**: I surface ___ loudly and swallow ___ because ___.

### What I rejected

- I considered ___ and rejected it because ___ (cost / time / complexity).
- I did not add ___ — it would have taken ___ minutes and bought ___.

### What I would do with more time

- **Next hour**: ___
- **Next day**: ___
- **Known sharp edge**: ___ will break if ___.
```

If you can only fill one section, fill "what I would do with more time." It is
the one that shows you know where the limits are.

---

## Retry and wall-clock math

`_client()` sets `timeout=30.0, max_retries=2`. The SDK retries connection
errors and 408/409/429/5xx with exponential backoff on its own.

**Do not wrap these calls in your own retry loop.** You would multiply attempts
rather than add resilience, and you would turn a 90-second worst case into a
several-minute one while your deadline runs.

```
worst-case wall clock = timeout * (max_retries + 1)
                      = 30s * 3
                      = 90s per call
```

Pick numbers you can defend against your own deadline. If you have a 10-minute
budget and three sequential calls, the defaults already consume 4.5 minutes in
the worst case. `_client(timeout=15.0, max_retries=1)` halves that. Passing
`max_retries=0` disables SDK retries entirely — reasonable for an interactive
demo where you would rather fail fast and rerun.

---

## Why this duplicates `observability/` on purpose

The scaffold's `observability/` tree does token accounting, span attributes,
and finish-reason recording properly, with OpenTelemetry behind it. This kit
does a shabbier version of the same concepts with `logging.getLogger`.

**Do not DRY them together.** They run in different environments:

- `observability/` runs *inside a rendered project* — it can assume a settings
  module, a dependency tree, and an OTel exporter.
- `llm_kit` runs *where none of that exists*. Its only allowed imports are the
  stdlib and `anthropic`. The moment it imports from the scaffold, it stops
  being copy-pasteable and stops solving the problem it exists for.

The duplication is the feature. Expect them to drift; that is fine. If you find
yourself adding a scaffold import here to remove repetition, you are deleting
the kit's reason to exist.

---

## What each function protects you from

| Function | The silent failure it makes loud |
|---|---|
| `_client()` | Unbounded hangs; accidental retry-on-retry |
| `call()` | Returning only text, throwing away `usage` and `stop_reason` |
| `text_of()` | Truncation reading as a short answer; empty content reading as "nothing to say" |
| `usage_of()` | `print()`-based token accounting that vanishes in production |
| `cost_of()` | Discovering the bill after the demo; unknown models reporting `$0.00` |
| `guard_tokens()` | A 400 you could have predicted; `tiktoken` undercounting Claude by 15–20% |
| `parsed()` | Regex-parsing JSON out of prose |

Notably absent: a `temperature` parameter. Claude Opus 5 and the other
thinking-by-default models **reject `temperature`, `top_p`, and `top_k` with a
400**. Pass one through `**kwargs` only if you have checked your model accepts
it.
