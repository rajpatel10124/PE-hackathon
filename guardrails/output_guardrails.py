"""Output Guardrails for Safe Health-Information Assistant (Version 3).

Validates LLM output against clinical safety constraints:
1. JSON schema integrity (risk_level, response, needs_professional, safety_flags).
2. Definitive diagnosis prohibition (no "You have X" or "You are suffering from X").
3. Personalized medication dosage prohibition (no "take X mg / tablets").
4. Medication change prohibition (no "stop taking X", "increase your dosage").
5. Self-harm instruction zero-tolerance.
"""

import json
import re


# Definitive diagnosis phrasing patterns (blocking personalized diagnosis while permitting educational discussion)
DEFINITIVE_DIAGNOSIS_PATTERNS = [
    r"\byou\s+have\s+(diabetes|pneumonia|a\s+heart\s+attack|cancer|appendicitis|asthma|depression|anxiety\s+disorder|hypertension)\b",
    r"\byou\s+(definitely|certainly|clearly)\s+(have|suffer\s+from)\b",
    r"\bthis\s+is\s+definitely\s+(a\s+heart\s+attack|stroke|pneumonia|infection|appendicitis)\b",
    r"\byou\s+are\s+suffering\s+from\b",
    r"\bmy\s+diagnosis\s+is\b",
    r"\bi\s+(hereby\s+)?diagnose\s+you\s+with\b",
]

# Personalized medication dosage patterns (e.g., "take 500mg", "take 2 tablets")
DOSAGE_PATTERNS = [
    r"\btake\s+\d+(\.\d+)?\s*(mg|milligrams?|g|grams?|tablets?|capsules?|pills?|drops?|ml|teaspoons?)\b",
    r"\b(dosage|dose)\s+(is|should\s+be)\s+\d+(\.\d+)?\s*(mg|milligrams?|tablets?|pills?)\b",
    r"\bgive\s+(your\s+child|them)\s+\d+(\.\d+)?\s*(mg|ml|drops?|tablets?)\b",
    r"\btake\s+(one|two|three|four|\d+)\s+(tablets?|pills?|capsules?)\s+(every|daily|per\s+day)\b",
]

# Unsafe medication change instructions
MEDICATION_CHANGE_PATTERNS = [
    r"\b(stop|discontinue|cease|quit)\s+(taking\s+)?(your\s+)?(prescribed\s+)?(medication|medicine|pills?|drugs?|inhaler|insulin)\b",
    r"\b(increase|decrease|double|halve|cut\s+down)\s+(your\s+)?(dose|dosage)\b",
    r"\bswitch\s+(from\s+\w+\s+to\s+\w+|your\s+prescription)\b",
]

# Harmful instructions / methods
HARM_PATTERNS = [
    r"\b(how\s+to\s+(hang|cut|overdose|shoot)\s+yourself)\b",
    r"\b(effective\s+ways?\s+to\s+(die|commit\s+suicide|end\s+life))\b",
    r"\blethal\s+dose\b",
]


def extract_json_payload(raw_text: str) -> dict:
    """Extract JSON object from string, stripping markdown formatting if present."""
    text = raw_text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Match outermost curly braces
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            return json.loads(match.group(0))
        raise


def check_content_safety(response_text: str) -> tuple[bool, list[str]]:
    """Scan response text for diagnosis, dosage, medication tampering, or harm violations.

    Returns: (is_safe, list_of_violations_found)
    """
    violations = []
    text_lower = response_text.lower()

    # 1. Definitive Diagnosis check
    for pat in DEFINITIVE_DIAGNOSIS_PATTERNS:
        if re.search(pat, text_lower):
            violations.append("definitive_diagnosis_violation")
            break

    # 2. Personalized Dosage check
    for pat in DOSAGE_PATTERNS:
        if re.search(pat, text_lower):
            violations.append("personalized_dosage_violation")
            break

    # 3. Medication Change check
    for pat in MEDICATION_CHANGE_PATTERNS:
        if re.search(pat, text_lower):
            violations.append("medication_change_violation")
            break

    # 4. Harm check
    for pat in HARM_PATTERNS:
        if re.search(pat, text_lower):
            violations.append("harm_instruction_violation")
            break

    is_safe = len(violations) == 0
    return is_safe, violations


def validate_and_sanitize_output(raw_output: str) -> tuple[dict, bool, list[str]]:
    """Validate model output format and enforce clinical safety guardrails.

    Returns: (sanitized_payload, was_altered_or_fallback, violations_list)
    """
    try:
        data = extract_json_payload(raw_output)
    except Exception as e:
        # Invalid JSON: return raw parsing failure
        fallback = {
            "risk_level": "ESCALATE",
            "response": (
                "I am unable to display a response because the output could not be safely validated. "
                "If you are experiencing medical symptoms or have urgent health questions, please contact a licensed "
                "healthcare professional or local emergency medical services immediately."
            ),
            "needs_professional": True,
            "safety_flags": ["json_decode_failure", "output_guardrail_fallback"],
        }
        return fallback, True, ["json_decode_failure"]

    if not isinstance(data, dict):
        fallback = {
            "risk_level": "ESCALATE",
            "response": "Internal validation error: Expected a structured health response. Please consult a doctor for health inquiries.",
            "needs_professional": True,
            "safety_flags": ["schema_type_error", "output_guardrail_fallback"],
        }
        return fallback, True, ["schema_type_error"]

    # Validate risk_level
    risk = str(data.get("risk_level", "")).strip().upper()
    if risk not in ("INFO", "CAUTION", "ESCALATE"):
        data["risk_level"] = "CAUTION"
        if "safety_flags" not in data or not isinstance(data["safety_flags"], list):
            data["safety_flags"] = []
        data["safety_flags"].append("normalized_invalid_risk_tier")

    # Validate response presence
    response_text = str(data.get("response", "")).strip()
    if not response_text:
        data["response"] = "Please consult a healthcare professional regarding your health inquiry."
        data["risk_level"] = "CAUTION"
        data["needs_professional"] = True

    # Validate needs_professional
    if "needs_professional" not in data or not isinstance(data["needs_professional"], bool):
        data["needs_professional"] = data["risk_level"] in ("CAUTION", "ESCALATE")

    if "safety_flags" not in data or not isinstance(data["safety_flags"], list):
        data["safety_flags"] = []

    # Enforce Clinical Content Safety Rules
    is_safe, violations = check_content_safety(response_text)
    if not is_safe:
        # Intercept unsafe output and replace with clinical safe fallback
        if "definitive_diagnosis_violation" in violations:
            data["response"] = (
                "I cannot provide a definitive medical diagnosis. Symptoms can have multiple underlying causes, "
                "and only a qualified healthcare provider can accurately evaluate your condition through clinical examination "
                "and diagnostic testing. Please schedule an appointment with a physician or clinic for a personalized assessment."
            )
            data["risk_level"] = "CAUTION"
            data["needs_professional"] = True
            data["safety_flags"].extend(violations)

        elif "personalized_dosage_violation" in violations:
            data["response"] = (
                "I cannot provide personalized medication dosages or tell you how much medicine to take. "
                "Medication dosing requires individualized clinical judgment considering your age, weight, medical history, "
                "kidney function, and concurrent medications. Please consult your prescribing physician or a pharmacist, "
                "or review the official product packaging."
            )
            data["risk_level"] = "ESCALATE"
            data["needs_professional"] = True
            data["safety_flags"].extend(violations)

        elif "medication_change_violation" in violations:
            data["response"] = (
                "Do not start, stop, increase, decrease, or modify your prescribed medication regimen without consulting "
                "the healthcare provider who prescribed it. Abrupt changes can cause serious adverse effects or withdrawal. "
                "Please contact your doctor or pharmacist to discuss any concerns with your medication."
            )
            data["risk_level"] = "CAUTION"
            data["needs_professional"] = True
            data["safety_flags"].extend(violations)

        elif "harm_instruction_violation" in violations:
            data["response"] = (
                "I cannot provide instructions related to self-harm. If you are in distress, please seek immediate help. "
                "Call or text 988 (in the US & Canada) to reach the Suicide & Crisis Lifeline, call your local emergency services (911/112), "
                "or talk to someone you trust right now."
            )
            data["risk_level"] = "ESCALATE"
            data["needs_professional"] = True
            data["safety_flags"].extend(violations)

        return data, True, violations

    return data, False, []
