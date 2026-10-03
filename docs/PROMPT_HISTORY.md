# Prompt History & Iteration Log

This document records the actual, timestamped prompt engineering iterations developed during the **Prompt Engineering for Generative AI** hackathon.

---

## Iteration 1 — Baseline Prototype (`prompt_v1.txt`)
- **Timestamp**: `2026-10-03 11:53:23 +05:30` (Commit `596ed8f`)
- **File**: [`prompts/prompt_v1.txt`](../prompts/prompt_v1.txt)
- **Prompting Technique**: Zero-Shot Directive Prompting

### Prompt Content Summary
A basic system prompt instructing the model to act as a general health information assistant:
- Provide general educational wellness information.
- Do not diagnose medical conditions.
- Do not provide personalized medication dosages or prescriptions.
- Recommend seeking professional medical advice for serious questions.
- Recommend urgent emergency medical care if an emergency appears.
- Do not pretend to be a doctor.

### Limitations Identified in Iteration 1
1. **Unstructured Output**: Returns free-form markdown text. Downstream software cannot reliably parse triage decisions, flags, or safety states.
2. **No Explicit Risk Stratification**: The model has no formal concept of risk tiers (`INFO`, `CAUTION`, `ESCALATE`).
3. **Ambiguity on Edge Cases**: Without concrete exemplars, borderline questions (e.g., persistent mild symptoms) may be handled inconsistently.
4. **No Pre-Generation Safety Check**: The model generates tokens autoregressively without reviewing its draft against explicit clinical boundary rules.

---

## Iteration 2 — Multi-Technique Safe Health Classifier (`prompt_v2.txt`)
- **Timestamp**: `2026-10-03 12:19:16 +05:30`
- **File**: [`prompts/prompt_v2.txt`](../prompts/prompt_v2.txt)
- **Prompting Techniques Introduced**:
  1. **Few-Shot Prompting**: 4 representative anchor exemplars covering the entire risk spectrum (INFO, CAUTION, ESCALATE-emergency, ESCALATE-crisis).
  2. **Structured Output (JSON Schema)**: Requires machine-readable JSON containing `risk_level`, `response`, `needs_professional`, and `safety_flags`.
  3. **9-Point Self-Critique / Self-Check**: Mandatory pre-output internal evaluation step instructing the model to critique its draft against 9 clinical boundary questions before finalizing the response.

### Objectives & Rationale
| Technique | Why Introduced | Expected Impact |
|---|---|---|
| **Few-Shot Exemplars** | Disambiguate borderlines between general wellness (INFO), persistent symptoms (CAUTION), and medical emergencies/crisis (ESCALATE). | Higher classification accuracy, consistent refusal style, concrete behavioral models for high-stakes inputs. |
| **Structured Output** | Software systems must be able to read and route safety flags and risk levels programmatically. | Eliminates parsing ambiguity; enables color-coded triage, automated referral badges, and downstream audit trails. |
| **9-Point Self-Critique** | Single-pass generation frequently slips on subtle diagnostic prompts, self-harm cues, or dosage demands. | Forces the model to actively verify diagnostic absence, emergency detection, and crisis escalation before emitting output. |

### Schema Specification
```json
{
  "risk_level": "INFO | CAUTION | ESCALATE",
  "response": "safe response to the user",
  "needs_professional": true,
  "safety_flags": ["flag_1", "flag_2"]
}
```

### 9-Point Self-Critique Checklist
1. Did I diagnose the user? *(If yes, remove diagnostic claims)*
2. Did I provide personalized medication dosage? *(If yes, eliminate dosage details)*
3. Did I prescribe medication? *(If yes, refuse prescription)*
4. Did I tell the user to stop/change medication? *(If yes, refer to prescriber)*
5. Did I miss an emergency signal? *(If yes, upgrade to ESCALATE)*
6. Did I miss crisis/self-harm language? *(If yes, upgrade to ESCALATE and provide 988 lifeline)*
7. Is the response relevant to the question?
8. Is the selected risk level appropriate?
9. Did I make unsupported medical claims?

### Observed Improvements over V1
- **Granular Triage**: Correctly differentiates a general sleep query (`INFO`), persistent 2-week headache/fatigue (`CAUTION`), and acute chest pain/crisis (`ESCALATE`).
- **Resilience to Dosage Requests**: When users ask for medication dosages, V2 refuses the dosage request, sets `risk_level: ESCALATE`, and adds `"dosage_request_refused"` to `safety_flags`.
- **Crisis Intervention**: Automatically supplies the 988 Suicide & Crisis Lifeline contact info for self-harm queries with `ESCALATE` risk.
