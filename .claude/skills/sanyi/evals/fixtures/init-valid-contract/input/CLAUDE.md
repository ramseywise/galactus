# CLAUDE.md

Customer service agent. Python, no framework (direct API calls).

## Structure

- `config.py` — tunables (model, thresholds)
- `states.py` — agent state schema
- `prompts.py` — system prompts
- `guards.py` — safety guards (PII masking, escalation)
- `router.py` — request routing and response building
