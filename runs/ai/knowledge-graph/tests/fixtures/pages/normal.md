---
title: Judge Calibration
tags: [eval, judge]
summary: "Frontmatter says the judge drifts after every prompt change."
updated: 2026-10-30
---

# Judge Calibration

An LLM judge is a Method that must be calibrated against human labels before
its verdicts are trusted. Calibration is measured with
[[Expected Calibration Error|ECE]], and the [[Gold Set]] supplies the labels.

Position bias is a FailureMode that swapping answer order mitigates. Swapping answer order
mitigates position bias in pairwise judging.

Swapping answer order mitigates position bias in pairwise judging.

<!-- auto-linked -->
## Related

- [[Gold Set]] — prerequisite-for
- [[Pairwise Judging]] — related (same family)
