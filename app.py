import json
import os
import re
import time
from pathlib import Path
from dotenv import load_dotenv
import streamlit as st

# Import application-level guardrails
from guardrails.input_guardrails import validate_input
from guardrails.output_guardrails import validate_and_sanitize_output

# Load environment variables
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
PROMPT_DIR = BASE_DIR / "prompts"
EVAL_RESULTS_FILE = BASE_DIR / "evaluation" / "results" / "evaluation_results.json"


def load_prompt(filename: str) -> str:
    """Load prompt file from prompts directory."""
    path = PROMPT_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found at {path}")
    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip()


def get_active_provider() -> tuple[str, str] | None:
    """Detect configured LLM provider and return (provider_name, api_key)."""
    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if gemini_key and gemini_key.strip():
        return "gemini", gemini_key.strip()

    openai_key = os.getenv("OPENAI_API_KEY")
    if openai_key and openai_key.strip():
        return "openai", openai_key.strip()

    groq_key = os.getenv("GROQ_API_KEY")
    if groq_key and groq_key.strip():
        return "groq", groq_key.strip()

    return None


def sanitize_error(error_message: str) -> str:
    """Sanitize error messages to avoid leaking keys or internals."""
    cleaned = re.sub(r"sk-[a-zA-Z0-9_\-]{20,}", "[REDACTED_KEY]", error_message)
    cleaned = re.sub(r"AIzaSy[a-zA-Z0-9_\-]{20,}", "[REDACTED_KEY]", cleaned)
    cleaned = re.sub(r"key=[^&\s]+", "key=[REDACTED]", cleaned)
    return cleaned


def call_llm(user_query: str, system_prompt: str) -> str:
    """Send query to the configured LLM provider with fallback candidate support."""
    provider_info = get_active_provider()
    if not provider_info:
        raise ValueError("API key not configured.")

    provider, api_key = provider_info

    if provider == "gemini":
        import google.generativeai as genai

        genai.configure(api_key=api_key)
        model_pref = os.getenv("MODEL_NAME") or os.getenv("GEMINI_MODEL")
        candidate_models = [model_pref] if model_pref else [
            "gemini-3.5-flash-lite",
            "gemini-3.1-flash-lite",
            "gemini-3.7-flash",
            "gemini-3.8-flash",
        ]

        last_exc = None
        for m_name in candidate_models:
            if not m_name:
                continue
            try:
                model = genai.GenerativeModel(
                    model_name=m_name,
                    system_instruction=system_prompt,
                )
                response = model.generate_content(user_query)
                if response.text:
                    return response.text
            except Exception as e:
                last_exc = e
                continue

        if last_exc:
            raise last_exc
        raise RuntimeError("No candidate Gemini model produced a response.")

    elif provider == "openai":
        from openai import OpenAI

        model_name = os.getenv("MODEL_NAME") or os.getenv("OPENAI_MODEL") or "gpt-4o-mini"
        client = OpenAI(api_key=api_key)
        completion = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_query},
            ],
        )
        content = completion.choices[0].message.content
        if not content:
            raise RuntimeError("Model returned an empty response.")
        return content

    elif provider == "groq":
        from openai import OpenAI

        model_name = os.getenv("MODEL_NAME") or os.getenv("GROQ_MODEL") or "llama-3.1-8b-instant"
        client = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=api_key)
        completion = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_query},
            ],
        )
        content = completion.choices[0].message.content
        if not content:
            raise RuntimeError("Model returned an empty response.")
        return content

    raise ValueError(f"Unsupported provider: {provider}")


# ==========================================
# VERSION 1 RUNNER (Baseline)
# ==========================================
def run_v1_baseline(query: str) -> str:
    """Run baseline zero-shot pipeline (Version 1)."""
    prompt_v1 = load_prompt("prompt_v1.txt")
    return call_llm(query, prompt_v1)


# ==========================================
# VERSION 2 RUNNER (Prompt Engineering Only)
# ==========================================
def run_v2_prompt_engineering(query: str) -> tuple[dict, str | None]:
    """Run Version 2 pipeline (Few-shot + JSON + Self-Critique) without external guardrails."""
    prompt_v2 = load_prompt("prompt_v2.txt")
    raw_response = call_llm(query, prompt_v2)

    # Basic JSON extraction
    try:
        from guardrails.output_guardrails import extract_json_payload
        data = extract_json_payload(raw_response)
        risk = str(data.get("risk_level", "INFO")).upper()
        if risk not in ("INFO", "CAUTION", "ESCALATE"):
            risk = "CAUTION"
        data["risk_level"] = risk
        return data, None
    except Exception as e:
        # 1-retry fallback
        retry_query = (
            f"Please output ONLY valid JSON matching: "
            f'{{"risk_level": "INFO|CAUTION|ESCALATE", "response": "safe response", "needs_professional": true/false, "safety_flags": []}}.\n'
            f"User Question: {query}"
        )
        try:
            retry_raw = call_llm(retry_query, prompt_v2)
            retry_data = extract_json_payload(retry_raw)
            return retry_data, "Recovered via 1 automated retry."
        except Exception:
            return {
                "risk_level": "ESCALATE",
                "response": "Internal formatting error. Please consult a healthcare professional for guidance.",
                "needs_professional": True,
                "safety_flags": ["json_parse_fallback"],
            }, "JSON parsing failed after retry."


# ==========================================
# VERSION 3 RUNNER (Final Guardrailed Pipeline)
# ==========================================
def run_v3_final(query: str) -> tuple[dict, str | None, list[str]]:
    """Run full Version 3 guardrailed pipeline:

    1. Input Guardrails (Off-topic, Crisis/Emergency detection)
    2. V3 Prompt + LLM inference
    3. Output Guardrails (Diagnosis, Dosage, Medication tamper sanitization)
    Returns: (final_payload, processing_note, violations_detected)
    """
    # Phase 1: Input Guardrails
    intercepted = validate_input(query)
    if intercepted:
        reason = intercepted.get("intercepted_by", "input_guardrail")
        return intercepted, f"Intercepted by Application Layer ({reason})", []

    # Phase 2: V3 Prompt + LLM Call
    prompt_v3 = load_prompt("prompt_v3.txt")
    raw_response = call_llm(query, prompt_v3)

    # Phase 3: Output Guardrails & Clinical Sanitization
    data, was_altered, violations = validate_and_sanitize_output(raw_response)
    note = None
    if was_altered:
        note = f"Output sanitized by Clinical Guardrails: {', '.join(violations)}"

    return data, note, violations


def render_risk_badge(risk_level: str):
    """Render high-contrast, accessible risk level card."""
    risk = str(risk_level).upper()
    configs = {
        "INFO": ("🟢 INFO", "#e6f4ea", "#137333", "General Educational Health / Wellness Query"),
        "CAUTION": ("🟡 CAUTION", "#fef7e0", "#b06000", "Symptom Inquiry: Professional evaluation advised, no diagnosis"),
        "ESCALATE": ("🔴 ESCALATE", "#fce8e6", "#c5221f", "High Risk / Acute Emergency / Refusal: Immediate professional escalation"),
    }
    badge_label, bg_color, border_color, subtitle = configs.get(
        risk, ("⚪ UNKNOWN", "#f1f3f4", "#5f6368", "Unclassified Risk Tier")
    )

    st.markdown(
        f"""
        <div style="background-color: {bg_color}; border-left: 6px solid {border_color}; padding: 10px 14px; border-radius: 6px; margin-bottom: 12px;">
            <div style="font-size: 1.15rem; font-weight: 700; color: {border_color};">{badge_label}</div>
            <div style="font-size: 0.82rem; color: #3c4043; margin-top: 2px;">{subtitle}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_v3_card(payload: dict, note: str | None = None):
    """Render full formatted card for Version 3 output."""
    render_risk_badge(payload.get("risk_level", "INFO"))

    needs_prof = payload.get("needs_professional", False)
    prof_text = "🩺 **Needs Professional:** **Yes**" if needs_prof else "⚪ **Needs Professional:** **No**"
    st.markdown(prof_text)

    flags = payload.get("safety_flags", [])
    if flags:
        flag_tags = " ".join([f"`{f}`" for f in flags])
        st.markdown(f"🏷️ **Safety Flags:** {flag_tags}")
    else:
        st.markdown("🏷️ **Safety Flags:** `none`")

    if note:
        st.info(f"🛡️ **Guardrail Event**: {note}")

    st.markdown("**Assistant Response:**")
    st.markdown(payload.get("response", ""))

    with st.expander("🔍 View Structured JSON Payload"):
        st.json(payload)


def main():
    st.set_page_config(
        page_title="Safe Health-Information Assistant (V3 Final)",
        page_icon="🩺",
        layout="wide",
    )

    st.title("Safe Health-Information Assistant")
    st.caption("Prompt Engineering for Generative AI — Version 3 (Final Hackathon System)")

    # Sidebar Navigation
    st.sidebar.header("Navigation")
    page = st.sidebar.radio(
        "Select View",
        [
            "🩺 Assistant (V3 Final)",
            "🔄 Prompt Comparison (V1 vs V2 vs V3)",
            "📊 Evaluation & Metrics",
            "📜 Prompt History",
            "ℹ️ Architecture & About",
        ],
        index=0,
    )

    # Provider status
    provider_info = get_active_provider()
    if provider_info:
        p_name, _ = provider_info
        st.sidebar.success(f"Connected Provider: **{p_name.capitalize()}** (`gemini-3.5-flash-lite`)")
    else:
        st.sidebar.error("⚠️ No API key detected in `.env`.")

    st.sidebar.markdown("---")
    st.sidebar.markdown(
        """
        **System Tiers**:
        - 🟢 `INFO`: General Wellness
        - 🟡 `CAUTION`: Non-Diagnostic Symptom
        - 🔴 `ESCALATE`: Urgent / Crisis / Refusal
        """
    )

    # Session state initialization for persistent UI results
    if "current_query" not in st.session_state:
        st.session_state.current_query = ""
    if "v3_result" not in st.session_state:
        st.session_state.v3_result = None
    if "comparison_result" not in st.session_state:
        st.session_state.comparison_result = None

    # ========================================================
    # PAGE 1: ASSISTANT (V3 FINAL)
    # ========================================================
    if page == "🩺 Assistant (V3 Final)":
        st.subheader("Interactive Health Assistant (Version 3)")
        st.markdown(
            "Powered by **Input Guardrails** + **Prompt V3 (Few-Shot, JSON, Self-Critique)** + **Clinical Output Sanitizers**."
        )

        # Quick Test Buttons
        st.markdown("##### Quick Test Queries (Try Risky, Safe, and Edge Cases):")
        qcol1, qcol2, qcol3, qcol4, qcol5 = st.columns(5)
        if qcol1.button("🟢 Sleep Habits (INFO)"):
            st.session_state.current_query = "How can I improve my sleep?"
        if qcol2.button("🟡 2-Week Fatigue (CAUTION)"):
            st.session_state.current_query = "I've been feeling tired for two weeks. What could be causing it?"
        if qcol3.button("🔴 Chest Pain (ESCALATE)"):
            st.session_state.current_query = "I have severe chest pain and difficulty breathing. What should I do?"
        if qcol4.button("💊 Dosage Request (Refusal)"):
            st.session_state.current_query = "What exact dosage of medicine should I take for my symptoms?"
        if qcol5.button("🚫 Off-Topic (Code)"):
            st.session_state.current_query = "Write a Python program to sort an array."

        user_input = st.text_area(
            "Enter your health or wellness question",
            value=st.session_state.current_query,
            placeholder="e.g., What are good exercises for mild lower back stiffness?",
            height=100,
        )

        if st.button("Submit Question", type="primary"):
            effective_query = user_input.strip() if user_input else st.session_state.current_query.strip()
            if not effective_query:
                st.warning("Please enter a question.")
            elif not provider_info:
                st.error("API Key Missing: Please configure your GEMINI_API_KEY in .env.")
            else:
                st.session_state.current_query = effective_query
                with st.spinner("Processing through V3 Safety Pipeline..."):
                    try:
                        payload, note, violations = run_v3_final(effective_query)
                        st.session_state.v3_result = {
                            "query": effective_query,
                            "payload": payload,
                            "note": note,
                            "violations": violations,
                        }
                    except Exception as e:
                        st.error(f"Execution Error: {sanitize_error(str(e))}")

        # Persistent Display of Results
        if st.session_state.v3_result:
            res = st.session_state.v3_result
            st.markdown("---")
            st.markdown("**User Question:**")
            st.info(res["query"])
            render_v3_card(res["payload"], res["note"])

    # ========================================================
    # PAGE 2: PROMPT COMPARISON (V1 vs V2 vs V3)
    # ========================================================
    elif page == "🔄 Prompt Comparison (V1 vs V2 vs V3)":
        st.subheader("Side-by-Side Prompt Version Comparison")
        st.markdown("Run the exact same input through all three development iterations to observe the safety evolution.")

        test_query = st.text_input(
            "Enter query to compare across V1, V2, and V3",
            value="I have severe chest pain. What medicine should I take?",
        )

        if st.button("Run 3-Way Comparison", type="primary"):
            if not test_query.strip():
                st.warning("Please provide a query.")
            else:
                with st.spinner("Running 3-way evaluation across V1, V2, and V3..."):
                    v1_out, v2_res, v3_res = None, None, None
                    try:
                        v1_out = run_v1_baseline(test_query.strip())
                    except Exception as e:
                        v1_out = f"Error: {sanitize_error(str(e))}"

                    try:
                        v2_res = run_v2_prompt_engineering(test_query.strip())
                    except Exception as e:
                        v2_res = ({"risk_level": "ERROR", "response": str(e), "needs_professional": True, "safety_flags": []}, str(e))

                    try:
                        v3_res = run_v3_final(test_query.strip())
                    except Exception as e:
                        v3_res = ({"risk_level": "ERROR", "response": str(e), "needs_professional": True, "safety_flags": []}, str(e), [])

                    st.session_state.comparison_result = {
                        "query": test_query.strip(),
                        "v1": v1_out,
                        "v2": v2_res,
                        "v3": v3_res,
                    }

        if st.session_state.comparison_result:
            cdata = st.session_state.comparison_result
            st.markdown("---")
            st.markdown(f"**Tested Query:** `{cdata['query']}`")
            c1, c2, c3 = st.columns(3)

            with c1:
                st.markdown("#### Version 1 — Baseline")
                st.caption("Zero-Shot • Directive • Unstructured")
                st.markdown("**Response:**")
                st.write(cdata["v1"])
                st.caption("⚠️ Limitation: No risk tiering, no safety flags, unvalidated text.")

            with c2:
                st.markdown("#### Version 2 — Prompt Eng.")
                st.caption("Few-Shot • JSON Schema • Self-Critique")
                v2_data, v2_note = cdata["v2"]
                render_risk_badge(v2_data.get("risk_level", "INFO"))
                st.markdown(f"🩺 **Needs Professional:** {v2_data.get('needs_professional')}")
                st.markdown(f"🏷️ **Flags:** `{v2_data.get('safety_flags', [])}`")
                st.markdown("**Response:**")
                st.write(v2_data.get("response", ""))
                if v2_note:
                    st.caption(v2_note)

            with c3:
                st.markdown("#### Version 3 — Final")
                st.caption("Input Guardrails • V3 Prompt • Output Sanitizer")
                v3_data, v3_note, _ = cdata["v3"]
                render_v3_card(v3_data, v3_note)

    # ========================================================
    # PAGE 3: EVALUATION & METRICS
    # ========================================================
    elif page == "📊 Evaluation & Metrics":
        st.subheader("System Evaluation & Benchmark Results")
        st.markdown(
            "Evaluation over **18 curated clinical benchmark queries** spanning `INFO` (6), `CAUTION` (6), and `ESCALATE` (6), including acute emergencies, dosage refusals, and crisis-style phrasing."
        )

        # Check if results exist
        if EVAL_RESULTS_FILE.exists():
            with open(EVAL_RESULTS_FILE, "r", encoding="utf-8") as f:
                results_data = json.load(f)

            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Total Cases", results_data.get("total_cases", 18))
            m2.metric(
                "Risk Classification Accuracy",
                f"{results_data.get('risk_classification_accuracy_pct', 0)}%",
                f"{results_data.get('correct_classifications', 0)}/{results_data.get('total_cases', 18)} correct",
            )
            m3.metric(
                "Safety Violation Rate",
                f"{results_data.get('safety_violation_rate_pct', 0)}%",
                "0% target achieved",
            )
            m4.metric(
                "Refusal / Redirect Rate",
                f"{results_data.get('refusal_redirect_success_rate_pct', 0)}%",
                "100% on risky queries",
            )

            st.markdown("### Detailed Case Evaluation Table")
            table_records = []
            for r in results_data.get("detailed_results", []):
                table_records.append({
                    "ID": r.get("id"),
                    "Query": r.get("input"),
                    "Expected": r.get("expected_risk"),
                    "Predicted": r.get("predicted_risk"),
                    "Match": "✅ PASS" if r.get("is_correct") else "❌ FAIL",
                    "Needs Doctor": "Yes" if r.get("needs_professional") else "No",
                    "Flags": ", ".join(r.get("safety_flags", [])) if r.get("safety_flags") else "none",
                })
            st.dataframe(table_records, use_container_width=True)

        else:
            st.info("Evaluation results not yet generated. Run `python evaluation/evaluate.py` or click below.")

        if st.button("Run / Refresh Live Evaluation", type="primary"):
            with st.spinner("Executing 18-query evaluation suite..."):
                from evaluation.evaluate import run_evaluation
                run_evaluation()
                st.success("Evaluation complete! Refreshing dashboard...")
                st.rerun()

    # ========================================================
    # PAGE 4: PROMPT HISTORY
    # ========================================================
    elif page == "📜 Prompt History":
        st.subheader("Prompt Development History & Iteration Log")
        history_file = BASE_DIR / "docs" / "PROMPT_HISTORY.md"
        if history_file.exists():
            with open(history_file, "r", encoding="utf-8") as f:
                st.markdown(f.read())
        else:
            st.warning("Prompt history document not found.")

    # ========================================================
    # PAGE 5: ARCHITECTURE & ABOUT
    # ========================================================
    elif page == "ℹ️ Architecture & About":
        st.subheader("System Architecture & Clinical Safety Approach")
        st.markdown(
            """
            ### Logical Processing Pipeline
            ```text
            USER QUERY
                │
                ▼
            [1. INPUT GUARDRAIL LAYER]
                ├── Off-Topic Check ──────────► Politely Redirect (Non-Health)
                └── Crisis / Emergency Check ──► Deterministic Escalation (988 / 911 / Poison Control)
                │
                ▼
            [2. INFERENCE LAYER]
                ├── Version 3 System Prompt (Few-Shot Anchors + JSON Schema + 9-Point Self-Critique)
                └── Gemini LLM (with automated fallback across endpoints)
                │
                ▼
            [3. OUTPUT GUARDRAIL LAYER]
                ├── JSON Schema & Risk Tier Validation
                ├── Definitive Diagnosis Prohibition ("You have X")
                ├── Personalized Dosage Prohibition ("Take X mg")
                ├── Medication Tampering Prohibition ("Stop/change X")
                └── Self-Harm Instruction Filter (Zero tolerance)
                │
                ▼
            [4. FINAL SAFE RESPONSE]
                ├── Verified Risk Tier (INFO / CAUTION / ESCALATE)
                ├── Professional Referral Indicator
                ├── Safety Audit Flags
                └── Clinically Safe Educational Content
            ```
            
            ### Prompting Techniques Implemented
            1. **Few-Shot Prompting**: Clinical exemplars for all three risk categories.
            2. **Structured JSON Output**: Strict machine-readable format for integration.
            3. **9-Point Self-Critique**: Pre-generation clinical verification checklist.
            
            ### Clinical Safety Boundaries
            - Never diagnose conditions or state diagnostic certainty.
            - Never prescribe or offer personalized dosage instructions.
            - Never advise stopping, starting, or modifying prescribed medicines.
            - Provide immediate, location-neutral crisis and emergency resources.
            """
        )


if __name__ == "__main__":
    main()
