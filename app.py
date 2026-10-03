import os
import re
from pathlib import Path
from dotenv import load_dotenv
import streamlit as st

# Load environment variables from .env file if available
load_dotenv()

PROMPT_FILE = Path(__file__).parent / "prompts" / "prompt_v1.txt"


def load_system_prompt() -> str:
    """Load baseline system prompt from disk."""
    if not PROMPT_FILE.exists():
        raise FileNotFoundError(f"System prompt file not found at {PROMPT_FILE}")
    with open(PROMPT_FILE, "r", encoding="utf-8") as f:
        return f.read().strip()


def get_active_provider() -> tuple[str, str] | None:
    """Detect configured LLM provider and return (provider_name, api_key)."""
    # 1. Google Gemini
    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if gemini_key and gemini_key.strip():
        return "gemini", gemini_key.strip()

    # 2. OpenAI
    openai_key = os.getenv("OPENAI_API_KEY")
    if openai_key and openai_key.strip():
        return "openai", openai_key.strip()

    # 3. Groq
    groq_key = os.getenv("GROQ_API_KEY")
    if groq_key and groq_key.strip():
        return "groq", groq_key.strip()

    return None


def sanitize_error(error_message: str) -> str:
    """Sanitize error messages to avoid leaking keys or overly detailed internals."""
    cleaned = re.sub(r"sk-[a-zA-Z0-9_\-]{20,}", "[REDACTED_KEY]", error_message)
    cleaned = re.sub(r"AIzaSy[a-zA-Z0-9_\-]{20,}", "[REDACTED_KEY]", cleaned)
    # Strip sensitive query params or auth headers if reflected in raw strings
    cleaned = re.sub(r"key=[^&\s]+", "key=[REDACTED]", cleaned)
    return cleaned


def call_llm(user_query: str, system_prompt: str) -> str:
    """Send query to the configured LLM provider."""
    provider_info = get_active_provider()
    if not provider_info:
        raise ValueError("API key not configured.")

    provider, api_key = provider_info

    if provider == "gemini":
        import google.generativeai as genai

        genai.configure(api_key=api_key)
        model_name = os.getenv("MODEL_NAME") or os.getenv("GEMINI_MODEL") or "gemini-3.8-flash"
        model = genai.GenerativeModel(
            model_name=model_name,
            system_instruction=system_prompt,
        )
        response = model.generate_content(user_query)
        try:
            if not response.text:
                raise RuntimeError("Model returned an empty response.")
            return response.text
        except ValueError as e:
            return f"The model response could not be displayed: {str(e)}"

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


def main():
    st.set_page_config(
        page_title="Safe Health-Information Assistant",
        page_icon="🩺",
        layout="centered",
    )

    st.title("Safe Health-Information Assistant")
    st.subheader("Version 1 — Baseline Prototype")

    # Small baseline indicator badge at the top
    st.caption("🏷️ Version 1 — Baseline")

    # Configuration status
    provider_info = get_active_provider()
    if not provider_info:
        st.warning(
            "⚠️ **API Key Missing**: No API key found. Please set `GEMINI_API_KEY` (or `OPENAI_API_KEY`) "
            "in your `.env` file or environment variables to receive responses."
        )

    # Input form
    user_question = st.text_area(
        "Enter your health or wellness question",
        placeholder="e.g., What are some healthy lifestyle habits to improve cardiovascular endurance?",
        height=130,
    )

    ask_button = st.button("Ask Assistant", type="primary")

    if ask_button:
        if not user_question.strip():
            st.warning("Please enter a question before submitting.")
            return

        if not provider_info:
            st.error(
                "Configuration Error: API key is missing. "
                "Please configure GEMINI_API_KEY or OPENAI_API_KEY in your .env file."
            )
            return

        try:
            system_prompt = load_system_prompt()
        except Exception as e:
            st.error(f"Configuration Error: Unable to load system prompt: {sanitize_error(str(e))}")
            return

        with st.spinner("Consulting assistant..."):
            try:
                response_text = call_llm(user_question.strip(), system_prompt)
            except Exception as e:
                clean_err = sanitize_error(str(e))
                st.error(
                    f"AI Service Error: Failed to generate response ({clean_err}). "
                    "Please verify your API key, network connection, or quota."
                )
                return

        # Display requirements:
        # 1. User question
        # 2. AI response
        # 3. Small "Version 1 — Baseline" indicator
        st.markdown("---")
        st.caption("🏷️ Version 1 — Baseline")

        st.markdown("**User Question:**")
        st.info(user_question.strip())

        st.markdown("**AI Response:**")
        st.markdown(response_text)


if __name__ == "__main__":
    main()
