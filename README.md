# Safe Health-Information Assistant

**A Multi-Version Prototype for the Prompt Engineering for Generative AI Hackathon**

---

## 1. Problem Statement & Mission

> *"Give general wellness information, refuse diagnosis or dosage advice, and escalate to a professional when appropriate."*

The goal is to engineer a safe, resilient conversational health-information system. Across iterations, we evaluate how prompt engineering techniques mitigate clinical risks, refuse out-of-bounds requests (e.g. diagnoses, dosages, self-harm), and escalate medical emergencies.

---

## 2. Project Structure

```text
safe-health-information-assistant/
│
├── app.py                     # Streamlit application with V1/V2 side-by-side evaluation
├── prompts/
│   ├── prompt_v1.txt          # Version 1: Baseline directive prompt (zero-shot)
│   └── prompt_v2.txt          # Version 2: Advanced prompt (Few-shot + JSON + Self-Critique)
├── docs/
│   └── PROMPT_HISTORY.md      # Timestamped iteration log of prompt development
├── requirements.txt           # Python dependencies
├── .env.example               # Environment variable template
├── .gitignore                 # Secrets and environment exclusion
└── README.md                  # System documentation and version comparisons
```

---

## 3. Version Overviews

### Version 1 — Baseline Prototype
- **Purpose**: Establishes a minimal working baseline using basic zero-shot prompt instructions (`prompts/prompt_v1.txt`).
- **Behavior**: Provides general wellness advice, asks users to contact a doctor for serious questions, and cautions against diagnosis.
- **Output**: Unstructured plain text.
- **Limitations**: No risk stratification, no structured flags, vulnerable to subtle dosage/diagnostic framing, and cannot be programmatically validated by downstream software.

### Version 2 — Advanced Prompt Engineering
- **Purpose**: Demonstrates significant prompt engineering improvements by introducing formal risk classification, structured machine-readable output, and internal clinical self-critique.
- **Risk Tiers**:
  - `INFO`: General health, lifestyle, nutrition, and wellness education with no immediate safety concern.
  - `CAUTION`: Symptom inquiries requiring non-diagnostic educational information and strong recommendations for clinical follow-up.
  - `ESCALATE`: Acute emergencies, severe symptoms (e.g., chest pain, respiratory distress), crisis/self-harm language, or requests demanding personalized medication dosages/prescriptions.
- **Output**: Validated JSON payload parsed and validated before rendering:
  ```json
  {
    "risk_level": "INFO | CAUTION | ESCALATE",
    "response": "safe educational response",
    "needs_professional": true,
    "safety_flags": ["flag_name"]
  }
  ```
- **Resilience**: Features automatic 1-retry handling for malformed JSON, with a controlled safe fallback to `ESCALATE` if parsing fails.

---

## 4. Prompting Techniques Introduced in Version 2

| Technique | How It Is Implemented | Why It Was Introduced |
|---|---|---|
| **1. Few-Shot Prompting** | 4 concrete clinical anchors in `prompts/prompt_v2.txt` illustrating `INFO`, `CAUTION`, `ESCALATE (emergency)`, and `ESCALATE (crisis)` inputs and outputs. | Disambiguates complex clinical boundaries. Models struggle with zero-shot triage; few-shot examples clearly demonstrate tone, refusal phrasing, and flag generation. |
| **2. Structured Output** | Strict JSON schema requiring `risk_level`, `response`, `needs_professional`, and `safety_flags`. | Healthcare software cannot rely on free-form text. Structured output enables downstream triage logic, audit logging, and automated UI warning cards. |
| **3. Self-Critique / Self-Check** | Mandatory 9-point internal review step evaluated before emitting the final JSON output. | Suppresses autoregressive drift where models inadvertently speculate on a diagnosis or mention drug dosages. Forces active verification against self-harm and emergency signals. |

### The 9-Point Self-Critique Checklist
1. Did I diagnose the user?
2. Did I provide personalized medication dosage?
3. Did I prescribe medication?
4. Did I tell the user to stop/change medication?
5. Did I miss an emergency signal?
6. Did I miss crisis/self-harm language?
7. Is the response relevant to the question?
8. Is the selected risk level appropriate?
9. Did I make unsupported medical claims?

---

## 5. Setup & Running Instructions

### 1. Environment Setup
```bash
cd safe-health-information-assistant
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure API Key
Copy the template and provide your API key (e.g. Gemini from [Google AI Studio](https://aistudio.google.com/)):
```bash
cp .env.example .env
# Edit .env:
# GEMINI_API_KEY=AIzaSy...
```

### 3. Launch Streamlit Application
```bash
streamlit run app.py
```
Open `http://localhost:8501` in your browser.

---

## 6. How to Use the Comparison UI

The application features three evaluation modes accessible from the sidebar:
1. **🔄 Side-by-Side Comparison (V1 vs V2)** *(Default)*: Runs the exact same user query through both the V1 baseline prompt and V2 advanced prompt simultaneously.
2. **✨ Version 2 — Advanced Prompting**: Focuses on V2 triage cards, safety flags, and JSON payloads.
3. **🏷️ Version 1 — Baseline Prototype**: Preserves original V1 behavior.

**Quick Test Buttons** are provided in the UI to rapidly demonstrate:
- 🟢 `Sleep Habits` (Evaluates `INFO`)
- 🟡 `2-Week Fatigue` (Evaluates `CAUTION`)
- 🔴 `Chest Pain & Meds` (Evaluates `ESCALATE` dosage refusal)
- 🆘 `Crisis / Self-Harm` (Evaluates `ESCALATE` crisis helpline)

---

## 7. Known Limitations of Version 2

While Version 2 significantly elevates safety and triage consistency, it intentionally focuses on **in-prompt techniques**. The following limitations remain to be solved in Version 3:
1. **No External Guardrail Layer**: Relies on model compliance with prompt instructions. Deterministic regex filters, blocklists, and output sanitizers are not yet integrated.
2. **No Automated Off-Topic Filter**: Non-health questions (e.g. general math or code) are not yet trapped by a dedicated input classifier.
3. **Potential Hallucinations**: Model responses are not grounded against external clinical databases (RAG) or validated medical ontologies.
4. **Adversarial Jailbreaks**: Highly complex multi-turn prompt injection or fictional framing might still challenge prompt-only constraints.
