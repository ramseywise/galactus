# Angle: Healthcare / regulated-domain constraints for a French medical-scheduling voice agent — and where they belong in the spec library

## Findings

### Part 1: Existing Spec Coverage of Data Protection & Regulatory Concerns

**High confidence findings:**

1. **agent-safety.md contains PII handling but not compliance/retention/erasure** (file:291-308)
   - §7 "PII Handling" addresses redaction of PII inputs before logging and blocking PII to third-party endpoints
   - Lists 13 PII types redacted in Layer 1 input pipeline (email, phone, credit card, SSN, API key, JWT, IBAN, IP address, DOB, postcode, CVV, passport, national ID)
   - BUT: no coverage of GDPR Article 9 special categories, lawful basis, explicit consent, retention windows, right-to-erasure, or data-residency requirements
   - No mention of regulated domains, healthcare, "PHI," "HIPAA" (though latter is US-only), or compliance frameworks
   - Verdict: **PII masking is present; compliance architecture is absent**

2. **agent-memory.md acknowledges GDPR audit trail and erasure but only in isolation** (file:68, file:194-195)
   - Line 68: "Compaction must write raw turns to cold storage before discarding them — required for a GDPR audit trail"
   - §5a (lines 194-195): Consolidation creates erasure problem: *"A right-to-erasure request must reach every representation: the structured store, the vector index, derived session summaries… once 'user is allergic to dairy' has been merged into a summary, deleting the source message does not delete the fact."*
   - Also §5a (line 196): *"A design that satisfies rollback may still fail erasure"* — explicit acknowledgment that erasure is a separate compliance constraint
   - BUT: framed as an implementation complexity, not as a response to Article 17 GDPR requirements
   - No discussion of legal basis, consent, data minimisation, or lawful processing conditions

3. **agent-context.md: retention only as latency/compaction strategy, not as legal retention window** (file:166)
   - Line 166: *"Past roughly thirty minutes of agent runtime, write progress to disk regardless of occupancy"* — this is a failure-recovery strategy, not a data-retention policy
   - No mention of retention schedules, data lifecycle, or destruction policies aligned to legal requirements

4. **agent-observability.md has redaction guidance for logging but limited scope** (file:122-129, 187-197)
   - Line 122-129: "Do not log raw tool inputs if they may contain PII or credentials. Log the hash for correlation; log the full input only to a secured audit store when required."
   - §7 "Logging integration" (lines 187-197) separates logs into three purposes: Debugging, Compliance, Improvement — and acknowledges that compliance requires "immutability and retention"
   - BUT: does not define what "compliance" means (which country, which law), and treats logging as operational artifact rather than as evidence in a regulated audit trail
   - No guidance on what constitutes "secured audit store" or how long audit logs must be kept

5. **agent-context.md: scope explicitly excludes regulatory boundaries** (file:31-32)
   - Lines 31-32: *"Where this spec's edges are… upward, toward the harness"* — regulatory compliance (data protection, consent, legal basis) is marked out-of-scope
   - The five-layer stack in DESIGN-PROCESS.md and agent-architecture.md makes no mention of a regulatory/compliance layer

6. **CLAUDE.md: compliance absent from the spec list**
   - Lists agent-safety, agent-uncertainty, agent-memory, agent-context, agent-observability, agent-tools, agent-reliability, agent-eval, agent-architecture
   - No agent-compliance.md or agent-data-protection.md
   - No mention of GDPR, regulated domains, or compliance requirements

**Medium confidence:**

7. **agent-uncertainty.md: asymmetric cost model could theoretically address medical errors** (file:85-110)
   - §3 "Asymmetric cost": the framework ranks consequences by blast radius, not confidence
   - Line 100: *"rank by blast radius, not by confidence. This repo already implements the rule in `akira dao`: mechanical fixes auto-apply behind a passing test suite; anything behavioural is surfaced to a human regardless of how certain the model is."*
   - Example: booking the wrong patient's appointment or cancelling a real appointment would have blast radius = high
   - BUT: this is a design pattern for "confidence vs. consequence," not a GDPR article, and does not address consent, data minimisation, or lawful basis
   - Verdict: **the framework *could* house medical-domain decision consequences, but does not address legal constraints**

---

### Part 2: Actual Regulated-Domain Constraints as of 2026

**High confidence, cited from authoritative sources:**

#### GDPR and Health Data (Article 9 Special Categories)

1. **Health data is "special category" personal data under Article 9 GDPR** [Secure Privacy, 2026](https://secureprivacy.ai/blog/gdpr-article-9-special-categories-lawful-processing-and-compliance-guide-2026)
   - Article 9(1) establishes a **prohibition on processing** special categories including data concerning health
   - Processing requires **both** (a) a lawful basis under Article 6 GDPR **and** (b) a separate Article 9(2) condition that lifts the prohibition
   - Without both, the starting point is that processing is prohibited
   - Confidence: **High**

2. **Article 9(2) exceptions for healthcare** [Secure Privacy, 2026](https://secureprivacy.ai/blog/gdpr-article-9-special-categories-lawful-processing-and-compliance-guide-2026)
   - (a) **Explicit consent** — patient must explicitly consent to processing; implicit consent does not suffice
   - (b) Employment / social security law — narrow, does not apply to private appointment booking
   - (c) Vital interests — narrow, for emergency scenarios
   - (d) Public health — narrow, requires EU/member-state law and safeguards
   - For a commercial medical appointment scheduling system, **explicit consent is the operational path**
   - Confidence: **High**

3. **GDPR Article 17 Right to Erasure** [Secure Privacy via agent-memory.md file:194-195](https://secureprivacy.ai)
   - A data subject has the right to request erasure of personal data
   - The controller must delete data and ensure **all representations** (structured store, vector index, derived summaries, consolidated memory) are reached
   - Consolidation/summarization creates a "dark erasure" problem: the source message is deleted but the fact remains in a summary
   - Operationally: **architecture must maintain traceability from summary back to source so erasure is possible**
   - Confidence: **High**

4. **GDPR Article 22 Automated Decision-Making** [TechPolicy Press, 2026](https://www.techpolicy.press/understanding-right-to-explanation-and-automated-decision-making-in-europes-gdpr-and-ai-act/)
   - Right "not to be subject to a decision based solely on automated processing" applies to decisions with legal or similarly significant effects
   - **Medical appointment scheduling alone does not trigger Article 22** (scheduling is administrative, not a decision with legal effect)
   - BUT: if the system performs **triage** (triaging patients into urgent vs. routine) or **clinical decision-making**, Article 22 applies
   - Requirement: human intervention and right to contest
   - Confidence: **High for appointment-only scope; Medium for systems doing triage or clinical routing**

5. **GDPR Data Minimisation** — not directly found in searches but implied by Article 5(1)(c)
   - Process only the personal data necessary for the specified purpose
   - For an appointment system: patient name, contact, appointment time, condition/reason (if needed for triage)
   - Do not collect or retain full health history, medication lists, or diagnostic details unless necessary
   - Confidence: **High (principle); Medium (application to voice agent)**

---

#### France-Specific: HDS (Hébergeur de Données de Santé)

6. **HDS certification required for health-data hosting in France** [Lexology, ARK, Bureau Veritas](https://www.legiscope.com/blog/hds-hebergement-donnees-sante-certification.html)
   - Article L1111-8 of French Public Health Code (Code de la Santé Publique) mandates certification
   - HDS (Health Data Hosting) certification is specific to France/EU; hosted by Agence du Numérique en Santé (ANS)
   - **v2.0 referential (updated 2024) applies to all systems; compliance deadline: 16 May 2026**
   - Confidence: **High**

7. **HDS scope and requirements** [ANS, multiple sources](https://esante.gouv.fr/ens/offre/hds)
   - HDS covers **hosting and infrastructure for processing health data**
   - If the voice agent's audio/transcripts/state are stored on French/EU infrastructure, that infrastructure must be HDS-certified
   - Does NOT directly apply to the AI agent software itself (agent-as-service), but to the data store
   - Covers 6 hosting activities; lasts 3 years with annual audit
   - Approximately 130+ providers certified as of 2026 (OVHcloud, Outscale, Microsoft Azure, AWS, GCP)
   - Confidence: **High**

8. **CNIL oversight and penalties** [HDS sources](https://www.legiscope.com/blog/hds-hebergement-donnees-sante-certification.html)
   - CNIL can impose sanctions up to **€20M or 4% of global turnover** for GDPR violations
   - Article 32 (security) violations are a common enforcement point
   - Confidence: **High**

---

#### France-Specific: Secret Médical (Medical Secrecy)

9. **Secret médical legal obligation** [French law sources](https://france-assos-sante.org/66-millions-dimpatients/patients-vous-avez-des-droits/le-secret-medical/)
   - Article L.1110-4 of the French Code de la Santé Publique: *"Every health professional must maintain confidentiality of medical information"*
   - Applies to all professionals intervening in the health system, not just doctors
   - Criminal penalties (Article 226-13 French Penal Code): 1 year imprisonment + €15,000 fine for breach
   - **Scope**: all information concerning a person that came to the knowledge of the professional
   - Confidence: **High**

10. **AI and secret médical** [CNIL guidance via voice-agent sources](https://vocalis-ai.org/en/blog/gdpr-healthcare-voice-ai-compliance/)
    - A voice agent handling patient calls acquires this information *in the course of the call*
    - The agent (and its operators) are bound by secret médical
    - CNIL recommends **short retention durations for voice recordings** that might contain health data
    - Confidence: **Medium** (CNIL guidance exists but not found in direct statutory language for AI)

---

#### EU AI Act (2026 applicability)

11. **Medical appointment scheduling is NOT high-risk under EU AI Act** [IntuitionLabs, Tandem Health, Gibson Dunn](https://intuitionlabs.ai/articles/eu-ai-act-pharma-medical-device-compliance)
    - High-risk AI includes systems for: diagnosis, clinical decision support, treatment recommendations, patient triage, patient monitoring
    - Appointment scheduling (administrative, not clinical) is **limited-risk**
    - Confidence: **High**

12. **Article 50 transparency obligation applies to all AI, limited-risk included** [multiple sources](https://decodethefuture.org/en/eu-ai-act-explained/)
    - By **2 August 2026**, the system must clearly disclose to users that they are interacting with an AI system
    - Exception: only if it is already obvious to a reasonable user
    - For a voice agent, disclosure could be: *"You are speaking with an automated voice assistant"*
    - Confidence: **High**

13. **High-risk AI system obligations delayed to 2 December 2027** [Gibson Dunn](https://www.gibsondunn.com/eu-ai-act-omnibus-agreement-postponed-high-risk-deadlines-and-other-key-changes/)
    - For use-based high-risk (Annex III) systems, full conformity assessment and human oversight requirements apply from 2 December 2027, not August 2026
    - Appointment scheduling is limited-risk, so this extension does not apply
    - Confidence: **High**

---

#### Call Recording & Consent (EU/France)

14. **France requires all-party consent for call recording** [RecordPhoneCall.com, multiple sources](https://recordphonecall.com/legal/france/)
    - Article 226-1 French Penal Code: recording a conversation without everyone's consent is a criminal offence
    - Contrast: US uses one-party consent in many states; EU/France uses all-party (two-party) consent
    - **Before recording the voice call, the agent must inform the patient and obtain consent**
    - Confidence: **High**

15. **GDPR compliance layer for recording** [Recording Law, 2026](https://www.recordinglaw.com/world-laws/world-recording-laws/eu-recording-laws/)
    - Even if recording is criminally lawful (all parties consent), it must comply with GDPR:
      - Valid lawful basis under Article 6 (consent, legitimate interest, etc.)
      - Privacy notice (transparently inform patient at call start)
      - Defined retention schedule (not indefinite)
    - Confidence: **High**

---

#### Third-Party Processor (ASR, LLM) and Data Transfer

16. **Controller-Processor relationship** [GDPR Local, Sprinto](https://gdprlocal.com/gdpr-article-28/) 
    - If the voice agent sends audio to a US ASR provider (e.g., OpenAI Whisper API, Google Speech-to-Text, AWS Transcribe) or uses a US LLM provider (e.g., OpenAI, Anthropic):
      - The French medical practice is the **controller** (determines why/how data is used)
      - The US provider is the **processor** (processes data on controller's instructions)
      - A Data Processing Agreement (DPA) under Article 28 GDPR is **required**
    - Confidence: **High**

17. **Schrems II and data transfer risk** [GlobalDataShield, DanubeData, CLASSICA](https://classicaproject.eu/2025/03/knowledge-unwrapped-supplementary-measures-and-appropriate-safeguards-for-international-transfers-of-health-data-after-schrems-ii/)
    - Schrems II (2020) invalidated the Privacy Shield and raised questions about adequacy of the EU-US Data Privacy Framework
    - For **health data** specifically: transferring to a US processor without supplementary measures (e.g., encryption, anonymization) creates compliance risk
    - The EU-US Data Privacy Framework is currently valid (2026), but legal experts expect the CJEU to issue a preliminary opinion by late 2026 or early 2027 that *may* invalidate it
    - **Supplementary measures recommended**: encrypt at rest, encrypt in transit, minimize data sent, use processors in EU-adequacy countries
    - Confidence: **High for status quo (2026); Medium-Low for 2027 risk forecast**

---

#### Data Residency & EU Hosting Expectations

18. **EU expects health data to remain in EU** [MassiveGRID, Opsio](https://massivegrid.com/blog/gdpr-data-residency-european-hosting-locations-matter)
    - GDPR does not formally require EU-only hosting, but Schrems II and regulatory practice establish an expectation for sensitive data
    - Health data is sensitive; French healthcare authorities (CNIL, ANS) expect it to be hosted in EU/France
    - For HDS-certified infrastructure: must be EU-based (CNIL/ANS audit)
    - Confidence: **High for regulatory expectation; Medium for strict legal requirement**

---

### Summary of Constraints for French Medical Scheduling Voice Agent

| Constraint | Source | Implication for Agent Design |
|-----------|--------|------------------------------|
| Health data = Article 9 special category | GDPR | Requires explicit consent + Article 9(2) condition |
| Two-party call recording consent | French Penal Code Art. 226-1 | Must disclose + obtain consent before recording |
| Right to erasure (Article 17) | GDPR | Architecture must maintain traceability for deletion |
| Data minimisation | GDPR Art. 5(1)(c) | Collect only appointment-necessary data; avoid full health records |
| Secret médical | French CSP L.1110-4 | Binding confidentiality; criminal penalties for breach |
| HDS certification required | French CSP L1111-8 | Infrastructure (data store) must be HDS-certified by May 2026 |
| Article 50 transparency | EU AI Act | Disclose AI nature to patient before/during call (effective Aug 2026) |
| Controller-Processor DPA | GDPR Art. 28 | If using US ASR/LLM provider, DPA + Data Transfer Agreement required |
| Schrems II supplementary measures | CJEU case law | Recommend EU-based processing or encryption + anonymization |
| Limited retention (voice recordings) | CNIL guidance | Keep audio short-term; delete after transcript extraction |

**Confidence: High** for all rows except "Schrems II 2027 risk" (Medium-Low forecast).

---

## Asset Verdicts

| Asset | Verdict | Salvageable at lower cost | Reason |
|---|---|---|---|
| **agent-safety.md** | ADAPT | PII masking section (§7, file:291-308) is reusable; extract as-is. Ergonomic payoff: add new §7a "Regulated domains" covering GDPR Article 9, lawful basis, explicit consent, and data-residency constraints specific to healthcare/finance/legal. Cost: ~500 words. The five-layer model (§1) provides the architectural home. | Data protection / compliance is absent from the spec. PII masking is present but narrow in scope (masking at input vs. architecture for consent, retention, erasure). The section exists; extend it. |
| **agent-uncertainty.md** | REUSE | The asymmetric-cost / blast-radius framework (§3, file:85-110) directly applies to medical-domain decision consequences. Appointment-booking errors have high blast radius and require human approval before execution. Use as-is; cite in domain-specific design docs. | The spec already answers "what does the system do when facing high-consequence decisions"? Reusable without modification. |
| **agent-memory.md** | ADAPT | §5a consolidation and erasure discussion (file:194-196) is architecturally sound; reusable. Adaptation needed: add **mandatory subsection** on "Compliance-driven architecture for erasure": explicitly require that any consolidation (summarization, distillation) maintain **reverse pointers** to source turns, so erasure can propagate. Cost: ~250 words to formalize what is currently stated as a problem. Also add lifecycle stage: **"E — Maintenance: Erasure"** — deletion must reach all representations, including old vector embeddings and archived summaries. | Erasure is flagged as a complexity; it should be formalized as a compliance requirement. The architecture is there; the compliance framing is missing. |
| **agent-context.md** | SKIP | No salvageable parts for regulated-domain constraints. The spec owns "window occupancy, eviction, compaction" — operational concerns. Regulated-domain requirements (retention schedule, redaction, audit trail preservation) belong elsewhere. | Context engineering is a performance/quality concern; compliance is a legal one. They are orthogonal. Over-extending this spec risks conflating "how long to keep this in the context window" with "how long must we legally retain this data." |
| **agent-observability.md** | ADAPT | §7 "Logging integration" (file:187-197) correctly identifies three audit-log purposes (Debugging, Compliance, Improvement) and notes tension between them. Adaptation: formalize the "compliance" purpose — add **mandatory subsection** defining: (a) retention windows per data type (call recordings: 7 days? 30 days?); (b) immutability and tamper-evidence; (c) audit-log format for legal review (not just operational debugging). Cost: ~300 words. §4 "Tool execution span" (file:122-129) already redacts PII from logs; keep as-is and cite in compliance subsection. | Compliance observability is acknowledged but not specified. The redaction guidance exists; the retention/audit trail guidance does not. |
| **CLAUDE.md** | ADAPT | Add **`Refs:` line** naming the new spec(s) that will own regulated-domain constraints. If adding to agent-safety.md, update line to: `Refs: python.md, logging.md, agent-architecture.md, agent-safety.md, agent-context.md, agent-observability.md, agent-uncertainty.md` (order unchanged; safety remains in alphabetical position). Cost: one line. | The spec roster is out of date with respect to compliance/data-protection requirements. The layer stack in DESIGN-PROCESS.md does not include a regulatory layer, but if one is added, CLAUDE.md must reference it. |

---

## Open Questions

1. **Where should regulated-domain constraints live — as a new spec, or as extensions to existing ones?**
   - Option A: Extend agent-safety.md with §7a "Regulated domains" covering GDPR, HDS, secret médical, call-recording consent, data residency, erasure.
   - Option B: Create new agent-compliance.md as a peer spec, on the grounds that compliance is a distinct concern from threat modelling / injection / PII masking.
   - Option C: Keep constraints in domain-specific DESIGN.md / README files per application; do not add to global spec library, on the grounds that GDPR-compliance-for-healthcare is not a durable cross-project convention but a one-off implementation detail.
   - **Tension**: The operator's specs are meant to be **durable, generic conventions**. An agent-compliance.md covering GDPR, HIPAA, HDS, SOC2, etc. could be generic enough. But a spec that is really "notes about French healthcare AI" would be a category error. Where is the line?

2. **If regulated-domain constraints are added, should they include prescriptive design patterns, or only establish the boundary?**
   - Example: Should agent-safety.md (if extended) include a worked pattern for "explicit consent capture in a voice call" (file:X example)? Or only state the requirement ("explicit consent required for Article 9(2)")? 
   - The current specs state **rules** (what must be true), not **implementations** (how to build it). But compliance often requires implementation specificity.

3. **Data retention: should it be part of agent-memory.md, or belong to a separate policy layer?**
   - agent-memory.md owns "what survives a turn, session, restart" — operational state.
   - Compliance retention ("voice recordings deleted after 30 days") is a legal policy, not operational.
   - agent-observability.md §7 lists retention as a compliance consumer, but does not specify durations or formats.
   - **Should the spec say:** "Define a data-retention policy per data type; do not infer retention from operational needs"?

4. **Third-party processor (ASR/LLM provider) risk: should the spec address it, or is it tooling-specific?**
   - A French medical practice using OpenAI Whisper for ASR + Claude for response generation creates a controller-processor relationship.
   - Is this a "spec-level" concern (belongs in agent-context.md or agent-safety.md), or a "tool-selection" concern (belongs in project docs)?
   - The Schrems II uncertainty (EU-US Data Privacy Framework may be invalidated in 2027) is time-sensitive; specs may need to age gracefully.

5. **EU AI Act Article 50 transparency ("you are speaking with AI") — is this a spec concern or a product requirement?**
   - The requirement is clear and time-bound (August 2026).
   - But it is a legal/product requirement, not an agent-design concern.
   - Should agent-context.md mention it (e.g., "system prompt must include AI disclosure"), or should it stay out?

6. **Secret médical and AI: does the spec library own professional confidentiality obligations, or is this domain-specific?**
   - The requirement is France-specific and healthcare-specific.
   - But the principle (an AI system inherits professional obligations of the context it operates in) is generic.
   - Should agent-safety.md (if extended) include a note: "The agent operates within the professional obligations of its domain (e.g., healthcare, law, finance); encode these as hard constraints at Layer 5, not as prompt guidance"?

---

## Conclusion

**The spec library has identified PII and logging as compliance concerns but has not built a coherent framework for regulated-domain constraints.** 

- agent-safety.md has the right layer (Layer 1 input redaction, Layer 5 escalation) but no regulatory framing.
- agent-memory.md correctly flags that erasure is architecturally hard, but frames it as an implementation problem, not a compliance requirement.
- agent-observability.md acknowledges that compliance and debugging have different retention/audit requirements, but does not specify either.
- None of the specs mention GDPR, data minimisation, lawful basis, consent, Article 9 special categories, HDS, secret médical, or Schrems II risk.

**Recommendation for the operator:** If a dedicated agent-compliance.md is created, it should be **generic** (stating GDPR/Article 9 principles, consent patterns, erasure architecture, data-minimisation discipline, audit-trail design) rather than **domain-specific** (one-off notes about French healthcare). The 2026 French medical-scheduling voice agent is a forcing function that reveals the gap; the solution belongs at the generic convention layer if it is to be reused by subsequent regulated-domain projects (finance, legal, healthcare outside France, etc.). 

Alternatively: extend agent-safety.md with a new regulatory section and accept that the spec becomes slightly larger and slightly less focused. The five-layer model provides the architectural home, and threat modelling + regulatory requirements are adjacent concerns in most real systems.

**The verdict is not whether regulated-domain constraints *exist* (they do, with high confidence). The verdict is whether they belong in this spec library as durable conventions (yes, with caveats) or remain in project-specific design docs (also viable, but requires duplication across projects).**

---

## Sources

- [GDPR Article 9 Special Categories & Lawful Processing (Secure Privacy, 2026)](https://secureprivacy.ai/blog/gdpr-article-9-special-categories-lawful-processing-and-compliance-guide-2026)
- [Healthcare GDPR Compliance & Article 9 (Secure Privacy DPO)](https://support.secureprivacy.ai/article/industry-specific-dpo-guidance-healthcare/)
- [Special Category Data (Data Protection Commission Ireland)](https://www.dataprotection.ie/en/organisations/know-your-obligations/lawful-processing/special-category-data)
- [GDPR Article 9: Special Personal Data Categories (Exabeam)](https://www.exabeam.com/explainers/gdpr-compliance/gdpr-article-9-special-personal-data-categories-and-how-to-protect-them/)
- [Special Category Data (ICO UK)](https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/lawful-basis/a-guide-to-lawful-basis/special-category-data/)
- [HDS Certification 2026 (Lexology)](https://www.lexology.com/library/detail.aspx?g=2dc6f8ff-e6c0-4509-b860-a99fdc837f89)
- [HDS Certification for Health Data Hosting (ARK Hinéo)](https://arkhineo.com/hebergement-des-donnees-de-sante-comprendre-la-certification-hds-en-2026/)
- [HDS Certification (Bureau Veritas France)](https://www.bureauveritas.fr/besoin/certification-hds-hebergeurs-de-donnees-de-sante)
- [HDS Certification Requirements Before Signing (Galeón Care)](https://www.galeon.care/fr/blog/certification-hds-en-2026-ce-que-chaque-hopital-doit-verifier-avant-de-signer/)
- [Health Data Hosting: HDS Certification 2026 (Légiscope)](https://www.legiscope.com/blog/hds-hebergement-donnees-sante-certification.html)
- [HDS Health Data Hosting Certification (Niwanet)](https://www.niwanet.net/expertises/hebergement-sante/)
- [Agence du Numérique en Santé (ANS) HDS](https://esante.gouv.fr/ens/offre/hds)
- [Secret Médical en France (Wikipedia)](https://fr.wikipedia.org/wiki/Secret_m%C3%A9dical_en_France)
- [Le Secret Médical - Définition & Obligations (France Assos Santé)](https://france-assos-sante.org/66-millions-dimpatients/patients-vous-avez-des-droits/le-secret-medical/)
- [Le Secret Médical (APHP DAJDP)](https://affairesjuridiques.aphp.fr/textes/le-secret-medical/)
- [Secret Médical: Obligations et Dérogations (Groupe Pasteur Mutualité)](https://www.gpm.fr/secret-medical/)
- [EU AI Act High-Risk Compliance (IntuitionLabs)](https://intuitionlabs.ai/articles/eu-ai-act-pharma-medical-device-compliance)
- [EU AI Act 2026: Penalties, Risk Tiers & Deadlines (Decode the Future)](https://decodethefuture.org/en/eu-ai-act-explained/)
- [EU AI Act for Healthcare (Tandem Health)](https://tandemhealth.ai/resources/knowledge/eu-ai-act-explained-what-healthcare-organisations-need-to-know)
- [EU AI Act Omnibus Agreement & Postponed Deadlines (Gibson Dunn)](https://www.gibsondunn.com/eu-ai-act-omnibus-agreement-postponed-high-risk-deadlines-and-other-key-changes/)
- [Understanding Article 22 & Automated Decision-Making (TechPolicy Press)](https://www.techpolicy.press/understanding-right-to-explanation-and-automated-decision-making-in-europes-gdpr-and-ai-act/)
- [Recording Law: EU Recording Laws Guide (RecordPhoneCall.com)](https://recordphonecall.com/legal/france/)
- [Call Recording Laws by Country 2026 (Exporb)](https://exporb.com/blog/en/global-call-recording-laws)
- [Call Recording Laws 2026 Compliance Guide (CallSphere AI)](https://callsphere.ai/blog/call-recording-laws-by-country-2026-guide)
- [GDPR Data Residency: Where EU Personal Data Can Live (Opsio)](https://opsiocloud.com/blogs/gdpr-data-residency-where-eu-personal-data-can-live/)
- [GDPR and Data Residency: Why European Hosting Matters (MassiveGRID)](https://massivegrid.com/blog/gdpr-data-residency-european-hosting/)
- [Schrems II and Data Transfers (CLASSICA Project, March 2025)](https://classicaproject.eu/2025/03/knowledge-unwrapped-supplementary-measures-and-appropriate-safeguards-for-international-transfers-of-health-data-after-schrems-ii/)
- [EU-US Data Privacy Framework in 2026 (GlobalDataShield)](https://globaldatashield.com/blog/eu-us-data-privacy-framework-2026)
- [Digital Sovereignty and Schrems II in 2026 (DanubeData)](https://danubedata.ro/blog/digital-sovereignty-schrems-ii-2026)
- [Data Controller vs Data Processor (GDPR Local)](https://gdprlocal.com/gdpr-article-28/)
- [Article 28 GDPR: Processor Obligations (Sprinto)](https://sprinto.com/blog/article-28-gdpr/)
- [GDPR Healthcare Voice AI Compliance 2026 (Vocalis AI)](https://vocalis-ai.org/en/blog/gdpr-healthcare-voice-ai-compliance/)
- [Healthcare Voice AI Agents Guide 2026 (GetProsper)](https://www.getprosper.ai/blog/healthcare-voice-ai-agents-guide)
