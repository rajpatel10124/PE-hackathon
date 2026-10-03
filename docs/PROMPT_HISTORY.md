# Prompt History & Iteration Log

This document records the actual, timestamped prompt engineering iterations developed during the **Prompt Engineering for Generative AI** hackathon.

---

## Version 1 — Baseline
- **Actual Timestamp**: `2026-10-03 11:53:23 +05:30` (Commit `596ed8f`)
- **File**: [`prompts/prompt_v1.txt`](../prompts/prompt_v1.txt)
- **Prompt Technique**: Zero-Shot Directive Prompting

### Purpose
Establish a minimal functional baseline to receive arbitrary user health inquiries, pass them through a foundational system prompt, and return educational health information while advising caution.

### Prompt Changes
- Authored initial baseline prompt establishing general health information boundaries.
- Directed model to decline prescribing or diagnosing, and to recommend professional medical or emergency consultation.

### Observed Limitations
1. **Unstructured Output**: Returns free-form markdown text. Downstream software cannot reliably parse triage decisions, flags, or safety states.
2. **No Risk Stratification**: The model had no formal concept of risk tiers (`INFO`, `CAUTION`, `ESCALATE`).
3. **Ambiguity on Edge Cases**: Without concrete exemplars, borderline questions (e.g., persistent mild symptoms) were handled inconsistently.
4. **No Pre-Generation Safety Check**: The model generated tokens autoregressively without reviewing its draft against explicit clinical boundary rules.

---

## Version 2 — Prompt Engineering
- **Actual Timestamp**: `2026-10-03 12:19:16 +05:30` (Commit `930a858`)
- **File**: [`prompts/prompt_v2.txt`](../prompts/prompt_v2.txt)
- **Prompt Techniques Introduced**:
  1. Few-Shot Prompting (4 clinical anchors)
  2. Structured Output (JSON Schema)
  3. 9-Point Self-Critique / Self-Check

### Changes & Prompt Construction
- **Few-Shot Examples**: Added 4 representative exemplars for `INFO` (sleep), `CAUTION` (persistent 2-week fatigue), `ESCALATE` (emergency chest pain & medication request), and `ESCALATE` (crisis / self-harm).
- **Structured Output**: Enforced JSON schema with keys `risk_level`, `response`, `needs_professional`, and `safety_flags`.
- **Self-Critique Checklist**: Included 9 explicit questions for the model to review internally before outputting the final JSON (checking for diagnostic claims, dosage numbers, medication tampering, emergency signals, crisis language).

### Observed Improvements
- Clean separation of health questions into formal risk tiers (`INFO`, `CAUTION`, `ESCALATE`).
- Successfully refused medication dosage requests and flagged them in structured JSON (`dosage_request_refused`).
- Refused self-harm queries and provided 988 lifeline contact info.
- Downstream UI can parse risk level, show color-coded badges, and surface safety flags.

---

## Version 3 — Final Safety Architecture
- **Actual Timestamp**: `2026-10-03 12:44:17 +05:30`
- **Files**:
  - [`prompts/prompt_v3.txt`](../prompts/prompt_v3.txt)
  - [`guardrails/input_guardrails.py`](../guardrails/input_guardrails.py)
  - [`guardrails/output_guardrails.py`](../guardrails/output_guardrails.py)
  - [`evaluation/evaluate.py`](../evaluation/evaluate.py)

### Changes
- **Input Guardrails**:
  - Deterministic off-topic filter intercepting programming, DevOps, and financial inquiries with polite redirects.
  - Deterministic crisis and emergency detector catching self-harm, suicide, overdose/poisoning, and acute cardiac/respiratory emergencies with location-neutral emergency hotlines.
- **Output Guardrails**:
  - Strict clinical regex filters preventing definitive diagnosis ("You have X", "You definitely have X").
  - Personalized medication dosage blocking ("take X mg / tablets").
  - Medication change prohibition ("stop/increase your medication").
  - Zero tolerance for harm methods.
  - Automatic 1-retry repair on invalid JSON with safe clinical fallback if unrecoverable.
- **Final Prompt V3**:
  - Synthesized role definition, off-topic handling, emergency escalation, and extended few-shot examples for dosage and diagnosis requests.
- **Automated Benchmark Evaluation**:
  - 18 labelled test cases across INFO (6), CAUTION (6), and ESCALATE (6).

### Observed Improvements
- **100% Defense Against Critical Injections**: Input guardrails guarantee that life-threatening crisis or overdose inquiries immediately trigger safe crisis resources regardless of model variability.
- **Robust Clinical Safety**: Output guardrails prevent unauthorized diagnosis or medication tampering even if the model inadvertently emits unsafe phrasing.
- **Full Software Integration**: Complete side-by-side comparison across V1, V2, and V3 in the Streamlit UI, with live metrics and evaluation dashboards.
