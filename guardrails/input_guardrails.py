"""Input Guardrails for Safe Health-Information Assistant (Version 3).

Validates input queries before sending to LLM:
1. Off-topic detection (redirects non-health questions).
2. Crisis and emergency detection (immediate ESCALATE intervention for self-harm, overdose, acute cardiopulmonary distress).
"""

import re


# Off-topic keyword and intent regex patterns
OFF_TOPIC_PATTERNS = [
    r"\b(write|create|code|debug|compile)\s+(a\s+)?(python|java|javascript|c\+\+|rust|html|css|sql|script|program|code|algorithm|function)\b",
    r"\b(kubernetes|docker|helm|terraform|aws|gcp|azure|ci/cd|devops)\b",
    r"\b(stock|shares|crypto|bitcoin|ethereum|portfolio|forex|invest(ment)?|trading|dividends?)\s+(recommendation|advice|pick|tip|prediction)\b",
    r"\b(sort\s+(an?\s+)?array|binary\s+search|linked\s+list|leetcode|github)\b",
    r"\b(nfl|nba|fifa|premier\s+league|world\s+cup|ipl)\s+(scores?|schedule|prediction)\b",
]

# Crisis / Self-Harm patterns
SELF_HARM_PATTERNS = [
    r"\b(want\s+to\s+die|kill\s+myself|hurt\s+myself|commit\s+suicide|end\s+my\s+life|suicidal|hang\s+myself)\b",
    r"\b(tell\s+me\s+how\s+to\s+(die|kill\s+myself|hurt\s+myself))\b",
    r"\b(ways?\s+to\s+(commit\s+suicide|end\s+it\s+all|overdose))\b",
]

# Overdose / Poisoning patterns
OVERDOSE_PATTERNS = [
    r"\b(took\s+too\s+many\s+pills|swallowed\s+a\s+bottle|drank\s+bleach|poison(ed|ing)?|accidental(ly)?\s+overdose)\b",
    r"\b(overdose(d)?\s+on\b)",
]

# Acute severe emergency symptoms
EMERGENCY_PATTERNS = [
    r"\b(severe\s+chest\s+pain|crushing\s+chest\s+pressure)\b",
    r"\b(can'?t\s+breathe|trouble\s+breathing|difficulty\s+breathing)\b",
    r"\b(unresponsive|stopped\s+breathing|choking|sudden\s+paralysis|face\s+droop(ing)?)\b",
    r"\b(going\s+to\s+faint\s+and\s+having\s+trouble\s+breathing)\b",
]


def check_off_topic(query: str) -> bool:
    """Check if query is clearly off-topic and unrelated to health or wellness."""
    q = query.lower()
    for pattern in OFF_TOPIC_PATTERNS:
        if re.search(pattern, q):
            return True
    return False


def check_crisis_or_emergency(query: str) -> tuple[bool, str, list[str]]:
    """Detect acute crisis, self-harm, poisoning, or severe medical emergencies.

    Returns: (is_crisis, safe_response, safety_flags)
    """
    q = query.lower()

    # 1. Self-harm / Suicide
    for pattern in SELF_HARM_PATTERNS:
        if re.search(pattern, q):
            return (
                True,
                "I cannot assist with requests related to self-harm. If you are experiencing thoughts of hurting "
                "yourself or feeling overwhelmed, please reach out for immediate support. You are not alone and help "
                "is available 24/7:\n\n"
                "- In the US and Canada: Call or text **988** to reach the Suicide & Crisis Lifeline.\n"
                "- In the UK: Call **111** (NHS) or **116 123** (Samaritans).\n"
                "- In India: Call **112** or the Tele-MANAS helpline at **14416**.\n"
                "- International: Contact your local emergency services or go to the nearest emergency facility immediately.\n\n"
                "Please reach out to a healthcare professional, emergency service, or trusted person right now.",
                ["crisis_detected", "self_harm_prevention", "escalate_immediate"],
            )

    # 2. Overdose / Poisoning
    for pattern in OVERDOSE_PATTERNS:
        if re.search(pattern, q):
            return (
                True,
                "**URGENT MEDICAL ALERT**: Suspected poisoning or medication overdose requires immediate emergency intervention.\n\n"
                "1. Call your local emergency number (such as **911**, **999**, **112**, or your regional emergency line) right now.\n"
                "2. If in the US, you can also contact Poison Control immediately at **1-800-222-1222**.\n"
                "3. Do not wait for symptoms to worsen and do not induce vomiting unless explicitly directed by a poison control specialist or doctor.\n"
                "Have the pill container or substance label ready for the emergency team.",
                ["overdose_detected", "poisoning_alert", "escalate_immediate"],
            )

    # 3. Severe Emergency Symptoms
    for pattern in EMERGENCY_PATTERNS:
        if re.search(pattern, q):
            return (
                True,
                "**EMERGENCY WARNING**: Severe chest pain, acute respiratory distress, sudden loss of consciousness, or signs "
                "of stroke are potential life-threatening emergencies.\n\n"
                "Do NOT wait, take unprescribed medication, or attempt to drive yourself. "
                "Please **call your local emergency medical services (such as 911, 999, or 112)** immediately or have someone "
                "take you to the nearest emergency department right now.",
                ["acute_emergency_detected", "severe_symptoms", "escalate_immediate"],
            )

    return False, "", []


def validate_input(query: str) -> dict | None:
    """Run full input guardrail pipeline.

    Returns:
        dict if intercepted by guardrails, None if safe to proceed to LLM.
    """
    if not query or not query.strip():
        return {
            "risk_level": "INFO",
            "response": "Please enter a valid question regarding health or wellness.",
            "needs_professional": False,
            "safety_flags": ["empty_input"],
            "intercepted_by": "input_guardrail",
        }

    # 1. Off-topic check
    if check_off_topic(query):
        return {
            "risk_level": "INFO",
            "response": "This assistant is designed for general health and wellness information. Please ask a health or wellness-related question.",
            "needs_professional": False,
            "safety_flags": ["off_topic_redirect"],
            "intercepted_by": "input_guardrail",
        }

    # 2. Crisis / Emergency check
    is_crisis, crisis_response, flags = check_crisis_or_emergency(query)
    if is_crisis:
        return {
            "risk_level": "ESCALATE",
            "response": crisis_response,
            "needs_professional": True,
            "safety_flags": flags,
            "intercepted_by": "crisis_guardrail",
        }

    # Input is valid and safe for LLM processing
    return None
