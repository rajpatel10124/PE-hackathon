# Safe Health-Information Assistant

**Version 1 — Baseline Prototype**

A baseline conversational assistant designed for the **Prompt Engineering for Generative AI** hackathon.

---

## 1. Project Purpose & Problem Statement

### Problem Statement
> *"Give general wellness information, refuse diagnosis or dosage advice, and escalate to a professional when appropriate."*

The objective of this project is to develop an AI health-information assistant that safely answers general health and wellness questions while strictly refusing medical diagnoses, prescriptions, and dosage advice, redirecting high-risk cases to healthcare professionals or emergency services.

### Version 1 Scope
Version 1 is an **un-guardrailed baseline prototype**. Its purpose is to establish a genuine, functional end-to-end baseline (UI, model integration, prompt loading, and error handling) against which future prompt engineering techniques, risk classification tiers, and safety guardrails can be measured and evaluated.

---

## 2. Project Structure

```text
safe-health-information-assistant/
│
├── app.py              # Streamlit web application & LLM integration
├── prompts/
│   └── prompt_v1.txt   # Version 1 baseline system prompt
├── requirements.txt    # Project dependencies
├── .env.example        # Environment variable template
├── .gitignore          # Git exclusion rules
└── README.md           # Documentation and baseline limitations
```

---

## 3. How to Install Dependencies

### Prerequisites
- Python 3.10, 3.11, or 3.12
- An active virtual environment (recommended)

### Steps
1. Navigate to the project directory:
   ```bash
   cd safe-health-information-assistant
   ```

2. Create and activate a Python virtual environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. Install required packages:
   ```bash
   pip install -r requirements.txt
   ```

---

## 4. How to Configure the API Key

The assistant supports Google Gemini (default), OpenAI, and Groq. API keys are **never hardcoded** and are read securely from environment variables or a local `.env` file.

1. Copy the example configuration:
   ```bash
   cp .env.example .env
   ```

2. Open `.env` and set your preferred provider's API key:
   - For **Google Gemini**:
     ```env
     GEMINI_API_KEY=your_actual_gemini_api_key
     ```
   - For **OpenAI**:
     ```env
     OPENAI_API_KEY=your_actual_openai_api_key
     ```
   - For **Groq**:
     ```env
     GROQ_API_KEY=your_actual_groq_api_key
     ```

Alternatively, you can export the environment variable directly in your terminal:
```bash
export GEMINI_API_KEY="your_api_key_here"
```

---

## 5. How to Run the Streamlit Application

With the virtual environment activated and the API key configured:

```bash
streamlit run app.py
```

Once started, open your browser to the local URL displayed (typically `http://localhost:8501`).

---

## 6. What Version 1 Currently Does

- **Clean Baseline UI**: Features a simple, focused Streamlit interface with clear title, subtitle, input text area, and action button.
- **Genuine Arbitrary Query Processing**: Dynamically receives user inputs and submits them to the LLM—no hardcoded or scripted responses.
- **Baseline System Prompt**: Loads `prompts/prompt_v1.txt` containing foundational behavioral guidelines:
  - Provide general wellness and educational health information.
  - Refuse diagnosis, prescription, or dosage instructions.
  - Advise consulting healthcare professionals for serious queries.
  - Recommend urgent/emergency medical assistance in acute situations.
  - Do not impersonate a physician.
- **Clear Result Display**:
  1. Displays the user's submitted question.
  2. Displays the model's generated response.
  3. Displays a persistent `🏷️ Version 1 — Baseline` indicator.
- **Safe Error Handling**:
  - Missing API key triggers an actionable configuration alert instead of crashing.
  - Network, rate limit, or model API failures present sanitized user-friendly errors without exposing credentials or internal stack traces.

---

## 7. Known Limitations of Version 1

As an intentional baseline prototype, Version 1 has several known limitations that will be addressed in subsequent versions:

1. **No Application-Level Guardrails**: The application currently relies 100% on the LLM's adherence to the system prompt. There are no pre-inference or post-inference filters.
2. **No Risk Tier Classification**: Does not categorize queries into `INFO`, `CAUTION`, or `ESCALATE` tiers.
3. **No Off-Topic Filtering**: Non-health questions (e.g., coding, history, finance) are not yet intercepted or redirected.
4. **Adversarial / Jailbreak Susceptibility**: Sophisticated prompt injection, hypothetical framing ("In a hypothetical novel, how much insulin..."), or roleplay could potentially bypass the simple baseline instructions.
5. **No Hallucination or Fact-Checking Layer**: The model's medical assertions are not cross-referenced against validated medical databases.
6. **Zero-Shot Baseline Only**: Does not yet incorporate advanced prompt engineering techniques such as few-shot exemplars, structured Chain-of-Thought (CoT), or output schema enforcement.
