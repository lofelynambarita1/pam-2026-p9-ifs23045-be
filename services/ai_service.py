import logging
import requests
import json
from config import Config

logger = logging.getLogger(__name__)

# Compact schema — model fills it, no verbose examples needed
SYSTEM_PROMPT = (
    "Skincare expert. Return ONLY valid JSON, no markdown, no extra text:\n"
    '{"routine_title":"...","summary":"2-3 sentences",'
    '"morning_routine":[{"step":1,"name":"...","product_type":"...","instruction":"...","why":"..."}],'
    '"evening_routine":[{"step":1,"name":"...","product_type":"...","instruction":"...","why":"..."}],'
    '"product_recommendations":[{"category":"...","product_name":"...","brand":"...","price_range":"Rp ...","why_recommended":"..."}],'
    '"tips":["..."]}'
)

REQUIRED_KEYS = {"routine_title", "summary", "morning_routine", "evening_routine", "product_recommendations", "tips"}


def _validate_result(result: dict) -> dict:
    missing = REQUIRED_KEYS - result.keys()
    if missing:
        raise ValueError(f"Incomplete JSON from LLM — missing keys: {missing}")

    result["routine_title"] = str(result["routine_title"]).strip() or "Personalized Skincare Routine"
    result["summary"] = str(result["summary"]).strip()

    for key in ["morning_routine", "evening_routine", "product_recommendations", "tips"]:
        if not isinstance(result[key], list):
            raise ValueError(f"{key} must be a list")

    return result


def generate_skincare_routine(skin_type: str, skin_concerns: str, budget: str) -> dict:
    # Compact user prompt — just the facts, no repetition
    user_prompt = (
        f"Skin: {skin_type} | Concerns: {skin_concerns} | Budget: {budget} | Market: Indonesia\n"
        "Create morning+evening routine with product recs."
    )

    payload = {
        "token": Config.LLM_TOKEN,
        "chat": f"{SYSTEM_PROMPT}\n\n{user_prompt}"
    }

    response = requests.post(
        f"{Config.LLM_BASE_URL}/llm/chat",
        json=payload,
        timeout=90
    )

    if response.status_code != 200:
        logger.error("LLM API error: status=%s body=%s", response.status_code, response.text[:500])
        raise Exception("LLM API returned non-200 status")

    data = response.json()

    content = None
    if isinstance(data, dict):
        content = data.get("response") or data.get("message") or data.get("content") or data.get("text")
        if not content and "choices" in data:
            content = data["choices"][0]["message"]["content"]
    elif isinstance(data, str):
        content = data

    if not content:
        logger.error("Unexpected LLM response structure: %s", str(data)[:500])
        raise ValueError("Cannot extract content from LLM response")

    content = content.strip()
    if content.startswith("```"):
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]
    content = content.strip()

    try:
        result = json.loads(content)
    except json.JSONDecodeError as e:
        logger.error("LLM returned invalid JSON: %s | raw: %s", e, content[:500])
        raise ValueError("LLM returned invalid JSON") from e

    return _validate_result(result)