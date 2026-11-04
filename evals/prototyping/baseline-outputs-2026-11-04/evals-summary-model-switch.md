# summary-model-switch
Date: 2026-11-04
Status: RESEARCHED
Track: agent

## Research

### Summary
Have a stronger LLM judge check every claim in both models' summaries against the transcript, spend the PMs' hours confirming a sample of what it flags, and decide on a difference limit agreed before anyone sees results. Under stated assumptions this resolves a true gap of roughly 4 to 7 points in the share of summaries with a material fabrication, against about 24 points for PMs reading transcripts unaided. It will not show that the absolute rate is low, and at some call volumes the saving will not repay the evaluation, so check the saving first.

### Scope
**Investigated:** how to compare a current and a cheaper summarisation model with no labels, about 2,000 transcripts and about six PM-hours, for a one-off decision, with fabrication as the main risk.

**Out of scope:** building the harness, choosing the candidate model, ongoing monitoring, and runtime changes to the summariser.

**Track:** `agent`. This work calls models and fits none, so the routing was not ambiguous.

**Depth of reading:** I read Ramprasad 2024 and FaithBench through an extraction of each paper's HTML. LongEval, Prediction-Powered Inference (PPI), FActScore, Schroeder 2025 and Goyal & Durrett 2021 were read at abstract level, and Hanley 1983, Brysbaert 2019 and Feinstein 1990 through secondary summaries. Check the figures against the papers before quoting them outside this document.

**Simulation:** the review-design numbers come from a throwaway Monte Carlo simulation of my own, with assumed inputs. They show the relative size of each design, not a forecast of your results.

### Findings

**F1. Check the saving before spending review time. Confidence: Medium (the arithmetic is High; the inputs are assumed).**
The per-call saving may be too small to repay the evaluation. As an illustration, using [Anthropic's listed prices](https://platform.claude.com/docs/en/about-claude/pricing) (the actual pair of models is unknown):

| Item | Assumption | Cost |
|---|---|---|
| Current summary | Sonnet 5.5, 9k input and 500 output tokens | about 2.3¢ |
| Cheaper summary | Haiku 5.5, same tokens | about 0.1¢ |
| Judge, all 4,000 summaries | Opus 5.5, 3k output tokens, batch discount | about $190 |
| PM time | 6 hours at an assumed $100 per hour | about $600 |

That is about $800 before engineering time, against a saving of about 2.2¢ per call, so break-even is near 36,000 calls. If the 2,000 stored transcripts represent a year of volume, the evaluation takes about 18 years to pay back and the simplest answer is not to switch. The planner should get call volume and the real price gap first, because this can end the work.

**F2. PMs reading transcripts unaided cannot answer this question. Confidence: High.**
A 45-minute call is about 6,750 words (assuming 150 spoken words per minute), or about 28 minutes to read at [238 words per minute](https://www.gwern.net/doc/psychology/linguistics/2019-brysbaert.pdf). Six hours therefore covers about 12 transcript pairs. Simulated, that gives a margin of about ±24 points on the difference at a 10% base rate. Finding no fabrications in 24 summaries still allows a true rate of up to 11.7% ([rule of three](https://jamanetwork.com/journals/jama/article-abstract/389714), computed exactly).

**F3. The design that fits is a judge screening every claim, with PMs confirming a sample of the flags. Confidence: Medium.**
Statistically this is two-phase sampling. It uses plentiful, imperfect machine output alongside scarce human labels, as [PPI](https://arxiv.org/abs/2301.09633v4) does. Claim-level checking is the established unit: [FActScore](https://arxiv.org/abs/2305.14251) splits text into atomic facts, and [LongEval](https://arxiv.org/abs/2301.13298v1) reports clause-level judgments cutting inter-annotator standard deviation from 18.5 to 6.8. Both were tested on other kinds of text, not call transcripts.

Simulated 95% margin on the difference in *detected* fabrication rate, for a 10% incumbent base rate and no true difference:

| Review design | Good judge (catches 70%, 15% false alarms) | Weak judge (catches 50%, 30% false alarms) |
|---|---|---|
| PMs only, 12 pairs | ±23.6 pts (judge not used) | ±23.6 pts (judge not used) |
| 500 pairs, 150 PM checks | ±3.6 pts | ±3.7 pts |
| 2,000 pairs, 100 PM checks | ±4.0 pts | ±4.6 pts |
| 2,000 pairs, 150 PM checks | ±3.1 pts | ±3.7 pts |
| 2,000 pairs, 250 PM checks | ±2.6 pts | ±2.9 pts |

Three things the planner should take from this:
- **True gap:** a judge that misses errors shrinks the visible difference. Dividing the margin by the catch rate gives a resolvable true gap of about 4 points with the good judge and 7 with the weak one.
- **Corpus size:** going from 500 to 2,000 pairs adds little at this review budget. Running all 2,000 is justified mainly by subgroup coverage such as long calls, and only if the judge cost is trivial.
- **PM time:** this assumes about 2 minutes per flagged summary, which needs measuring. At a 2% base rate, about 91% of PM checks would be false alarms even with the good judge.

**F4. The evaluation can support a comparison, not an absolute safety claim. Confidence: High.**
Auditing the judge's unflagged claims is the expensive direction. Checking 100 unflagged claims and finding nothing wrong still allows a 2.95% miss rate per claim, which is about 26% per summary at 10 material claims. So confirmed fabrications are a floor on the true rate. The decision statement should read "no more than X points worse than the current model", and should separately report the current model's confirmed rate. If that floor is already uncomfortable, the current summaries are a problem regardless of the switch.

**F5. The judge is untrusted until it is calibrated, and two measures are needed. Confidence: Medium.**
- **Evidence on judges:** on dialogue, the [best prompt-based detector reached about 70% balanced accuracy on LLM summaries, and older automatic metrics about 40 to 50%](https://arxiv.org/html/2406.03487v1). On samples chosen because detectors disagreed, [FaithBench's best was 57.65%](https://arxiv.org/html/2410.13210v1). Both predate current models and use short texts, so neither predicts performance on long calls.
- **Repo rule:** `agent-eval.md:180` bars uncalibrated graders from release decisions, and `agent-eval.md:208-214` requires a verifier structurally stronger than the generator.
- **Precision:** PM confirmation of flags measures it directly.
- **Recall:** seeding known fabrications into summaries from both models measures it without PM time. Treat the result as an upper bound, because [simple synthetic errors do not match real ones](https://aclanthology.org/2021.naacl-main.114). What matters most is whether recall is similar for both models.
- **Deterministic check:** numbers, dates and names absent from the transcript can be found by code. This should only raise candidates, since "twenty percent" and "20%" will differ as text.

**F6. PMs should not see the judge's verdict or which model wrote the summary. Confidence: Medium.**
In a [pre-registered experiment with 350 annotators](https://aclanthology.org/2025.findings-acl.1323/), showing LLM suggestions did not speed people up, shifted the labels, and inflated the measured performance of LLMs. That study used crowdworkers on subjective tasks, not PMs on fact-checking. I found no study comparing blind and unblind review directly. Showing PMs the judge's located evidence is a real trade-off: it saves the time this design depends on, but it may also anchor them. Each check therefore needs a route to the full transcript.

**F7. The definition of "fabrication" has to be settled first, because inference is the hard case. Confidence: High for the need; Medium for the size.**
[About 38% of LLM dialogue-summary errors](https://arxiv.org/html/2406.03487v1) were plausible inferences the conversation never stated, such as a renewal intent read from tone. Those are exactly what an account manager might repeat. Agreement is also weak in this territory: 66.94% pairwise F1 between trained fact-checkers in that study, and [Krippendorff's alpha of 0.58 on FaithBench's three-way labels, with first-round agreement "as low as 0"](https://arxiv.org/html/2410.13210v1) before discussion.

The planner needs:
- A short rubric agreed by the PMs, covering materiality (commitments, pricing, dates, named people, competitors, renewal intent) and whether inference counts.
- Shared calibration on an overlapping set. Report raw agreement and the disagreements themselves, since [kappa behaves oddly at low prevalence](https://scholarhub.vn/publication/:slug/99d46fd7-7674-4728-9c1a-4edb5f5f85c5).
- Separate outcomes for "contradicted", "no evidence found", "cannot judge" and "judge failed to run", per `agent-uncertainty.md:50` and `:77`.

**F8. Fabrication alone can be gamed by a model that says less. Confidence: Medium.**
A shorter summary has fewer chances to be wrong. Report the rate per claim as well as per summary, and add a guard for omissions: summary length, coverage of what account managers need, and a small blind side-by-side read. This comes out of the same PM budget and I did not simulate it.

**F9. The comparison is only fair if both arms share inputs and a fixed setup. Confidence: High that it matters; the state of your stored data is unknown.**
- **Stored summaries:** these may span several prompts or model versions. If model and prompt version were not recorded (`agent-observability.md:83`), regenerate the current arm rather than trusting them.
- **Repeat runs:** one draw per transcript is acceptable, since each customer call gets one summary and the rate across transcripts is the claim. Report `n` (`agent-eval.md:58`).
- **Prompt tuning:** if the candidate's prompt is tuned, do it on transcripts outside the evaluated set.
- **Model snapshot:** results hold only for the pinned version evaluated (`agent-observability.md:24`).

**F10. Transcripts stand in for what was said, and they are imperfect. Confidence: Medium.**
Your concern is what was said on the call, but this design can only test against the transcript. Errors in speech recognition or speaker labels will look like support or like fabrication. Both arms read the same text, so the comparison is less exposed than the absolute rate. I found no controlled study isolating the effect of speaker-attribution errors on summary faithfulness. Spot-check audio for confirmed flags if audio still exists.

### Asset verdicts

| Asset | Verdict | Salvageable at lower cost | Reason |
|---|---|---|---|
| `.claude/specs/agent-eval.md` | ADAPT | n/a | Keep `unsupported_claim` (`:114`), grader states (§7) and asymmetric verification (§9). "Calibrated" (§7) relies on liked/disliked signals you do not have, so use F5 instead. Its 50 to 200 rows guidance (`:133`) is too loose here (see Disconfirming Evidence). |
| `.claude/specs/agent-eval.md` §5 regression and capability suites, §8 hill-climbing | SKIP | The debugging order at `:149-152` is worth keeping if scores look odd | Built for continuing programmes; this is a one-off decision. |
| `.claude/specs/agent-uncertainty.md` | ADAPT | n/a | The abstain-versus-failure distinction (`:77`) and consequence-first ranking (§3) apply. The rest is runtime design. |
| `runs/ai/marketing-comms/evals/run.py` | SKIP | The report shape: named metrics with `n`, plus a dry-run mode | Its grounding metric is token overlap, "a blunt proxy" by its own account (`:47-52`), and would pass a fabricated claim that reuses transcript words. |
| `runs/ai/marketing-comms/src/ingest/facts.py` `verify_facts` | ADAPT | n/a | Re-reading a cited span from the source (`:140-170`) is the right check that a judge's quoted evidence exists. Exact matching needs loosening for paraphrase. |
| `.claude/specs/models.md` | REUSE | n/a | "Pay for judgment, not for reading" (`:6`) supports a stronger judge than generator. |

### Assumptions
- **Assumption:** "A few hours" means about six PM-hours in total. — **Evidence:** the request gives no exact figure and nobody could be asked. — **If wrong:** margins change as in the F3 table; below about three hours the design gets close to unusable. — **Confidence:** Medium
- **Assumption:** A flagged summary takes about 2 minutes to check. — **Evidence:** my estimate, not measured. — **If wrong:** at 5 minutes, checks fall to about 60 and margins widen well beyond the table. Time the first few checks. — **Confidence:** Low
- **Assumption:** Calls run about 45 minutes, about 6,750 words. — **Evidence:** my estimate; no transcript data available. — **If wrong:** F1 and F2 scale with length, while F3 changes little. — **Confidence:** Low
- **Assumption:** Judge performance lies between the simulated good and weak profiles, at the summary level. — **Evidence:** loosely anchored on the balanced accuracies in F5. — **If wrong:** a weaker judge wastes PM time and hides differences, which F5's measures should reveal. — **Confidence:** Low
- **Assumption:** Simulated errors are moderately correlated within a transcript (30% of calls are "hard", at twice the base rate). — **Evidence:** a modelling choice. — **If wrong:** the unaided-PM margin in F2 moves somewhat; the order-of-magnitude gap should stay. — **Confidence:** Medium
- **Assumption:** No `/proto-design` stop is needed. — **Evidence:** a consumer and a cost of being wrong are both stated, and the question is an evaluation rather than a new system. — **If wrong:** the unquantified cost becomes a frame gap, surfacing as an inability to agree the limit in Key Unknowns. — **Confidence:** Medium
- **Assumption:** Transcripts may be sent to the judge's vendor. — **Evidence:** none; see `agent-safety.md:297` on third-party PII. — **If wrong:** the judge must come from an already-approved provider, or the design changes. — **Confidence:** Low

### Disconfirming Evidence
- **F1 (the saving may not repay the evaluation):** high volume or an expensive current model would overturn this. I could not check it, since neither is known. One serious customer incident could also outweigh any saving, which strengthens the case against switching.
- **F2 (unaided review fails):** a repo spec seems to contradict this, saying 50 to 200 rows suffice for most gates (`.claude/specs/agent-eval.md:133`). That line concerns cost control on LLM grading, not rare errors. Even with perfect labels, a paired test with 12% discordant pairs needs about 297 pairs for a 5-point limit, 825 for 3 points and 1,856 for 2 points (one-sided 5%, 80% power). Also, a much shorter call length would stretch PM coverage, but not by enough to matter.
- **F3 (judge plus sample):** FActScore reports an automated estimator within 2% of human scores, which suggests less human checking might do. I looked at this: it measures an aggregate score on biographies against a knowledge source, not rare errors in long conversations, so I did not rely on it. A judge whose errors depend on which model wrote the summary would bias the comparison. PPI's validity guarantee requires labelled data sampled as designed, which is why seeding (F5) and random selection of checks both matter.
- **F4 (no absolute claim):** a very high judge recall on seeded errors would narrow this, but seeded errors are easier than real ones. I found nothing that gives a cheap route to a tight absolute bound.
- **F5 (judges are unreliable):** the detector evidence uses older models, and FaithBench deliberately selected hard samples, so its numbers are a worst case. Current judges may do better. Calibration should show this directly.
- **Cheaper means less faithful:** I looked for this and it is not reliable. On FaithBench's hard samples, GPT-3.5-Turbo (44.26% unwanted) beat Claude-3.5-Sonnet (49.18%). So neither the worry nor the reassurance should be assumed.
- **F6 (blinding):** no direct test found, and PMs may behave differently from crowdworkers. Blinding costs little, so I kept it.
- **F7 (kappa):** some researchers dispute that the prevalence effect is a real problem (Vach 2005, seen only through a secondary summary). Reporting raw agreement and the disagreements holds either way.

### Key Unknowns
- **Call volume and price gap:** these settle F1 and may end the work.
- **The acceptable limit (X):** the account-management owner has to set it before results are seen. If they need tighter than about 4 to 7 points, this budget cannot deliver it. The options are then more review time, a runtime safeguard, or not switching.
- **The base rate:** nothing here gives a credible figure for long customer calls. Ramprasad's 23% (GPT-4, short dialogues) is the closest, and the first judge run will give a rough estimate.
- **Provenance of stored summaries:** which model and prompt produced them (F9).
- **PM agreement and speed:** both are unmeasured, and the design depends on both.
- **Audio retention and transcript quality:** this limits how far F10 can be checked.
- **Data terms:** whether transcripts may go to the candidate's or the judge's vendor.
- **Reversibility:** whether the switch can be staged and rolled back (`agent-uncertainty.md:124`). An easy rollback would justify accepting more uncertainty here.

### Recommendation
First confirm that the saving at real call volume justifies any evaluation, because it may not. If it does, the research supports a paired comparison on the same transcripts, using a judge stronger than either model to check material claims, with the PMs' hours spent on an agreed rubric and on blind confirmation of a random sample of flags. Seeded fabrications should measure what the judge misses. The account-management owner should fix the acceptable difference before results exist, knowing that this budget can resolve about 4 to 7 points and cannot certify an absolute rate. The result should be read as "not detectably worse by more than X", alongside the current model's confirmed rate and an omission check, and any failure to calibrate the judge should count as "no evidence to switch", not as a pass.
