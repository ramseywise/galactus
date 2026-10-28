# Context health — compact proactively

Sessions that grow past 150k context cost 5× more per turn (no cache benefit on the
overflow). 52% of spend is in this bucket. Compact aggressively:

- **Phase boundaries are compact boundaries.** After completing a plan step, finishing a
  skill invocation, or switching focus within a session — compact. Don't wait for the
  system to force it.
- **Before spawning subagents** that will re-derive context — compact the parent first
  so the spawn starts lean.
- **After large reads** (reading 5+ files, a full plan doc, or any file >500 lines) that
  won't be needed again — compact to shed them from the prefix.
- **The 30-turn heuristic**: if you've exchanged ~30 messages without compacting, you're
  likely past 150k. Compact.

The PreCompact hook timestamps plan docs automatically. Compacting is cheap (one turn);
carrying stale context is expensive (every subsequent turn).
