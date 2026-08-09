# Expected — wander on the user-cache diff

wander (Kiyoko) reads this diff and asks 3–5 **pointed questions about the decisions the
change walked past** — not a findings list, not edits. A good run surfaces the intent gaps
this diff leaves open. The diff introduces a module-level cache with no bounds and no
invalidation, and silently swallows a DB error into an empty dict that then gets cached.

## The decisions this diff walked past (a good wander names most of these)

1. **Unbounded cache lifetime / eviction.** `_CACHE` grows without limit and never expires.
   Is this a long-lived process? What's the expected key cardinality? Should it be an LRU
   or TTL cache?
2. **No invalidation on user update.** If a user record changes in the DB, cached callers
   keep the stale record forever. Is staleness acceptable here, or does something need to
   bust the cache on write?
3. **Swallowed error is cached as a real record.** `_fetch_from_db` turns a `DBError` into
   `{}`, and `get_user` then caches that empty dict — so a transient DB blip permanently
   pins a bad "user" in the cache. Was caching-the-failure intended, or should the empty
   result skip the cache?
4. **`{}` vs "not found" vs "error" are conflated.** Callers can't distinguish a real empty
   user, a missing user, and a failed lookup. Is that distinction needed downstream?
5. **Thread-safety.** A module-level dict mutated from `get_user` — is this called
   concurrently? If so the check-then-set is racy.

## What a BAD run looks like (grade these down)

- Restating what the code does ("this adds a cache") instead of asking about the decision.
- Producing a ranked findings list with severities (that's `scan`/Kaneda, not wander).
- Editing the file or proposing a patch (wander never mutates).
- Generic questions that could apply to any diff ("is this tested?" with no specific hook).
- More than 5 questions, or fewer than 3.
