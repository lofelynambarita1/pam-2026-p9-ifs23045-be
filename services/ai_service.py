import logging
import requests
import json
from config import Config

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a professional dermatologist and skincare expert. 
Given skin type, concerns, and budget, create a personalized skincare routine.
Respond ONLY with valid JSON, no markdown, no explanation:
{
  "routine_title": "Personalized Skincare Routine Title",
  "summary": "Brief 2-3 sentence summary of the overall approach and what to expect",
  "morning_routine": [
    {"step": 1, "name": "Cleanser", "product_type": "Gentle Foaming Cleanser", "instruction": "Apply to damp face, massage gently for 60 seconds, rinse with lukewarm water", "why": "Removes overnight sebum and prepares skin for absorption"}
  ],
  "evening_routine": [
    {"step": 1, "name": "Double Cleanse - Oil", "product_type": "Cleansing Oil/Balm", "instruction": "Massage onto dry skin to dissolve makeup and SPF, then emulsify with water", "why": "Effectively removes sunscreen and makeup residue"}
  ],
  "product_recommendations": [
    {"category": "Cleanser", "product_name": "Product Name", "brand": "Brand", "price_range": "Rp 50.000 - 150.000", "why_recommended": "Suitable for oily skin, non-comedogenic"}
  ],
  "tips": [
    "Always patch test new products for 24-48 hours before full application",
    "Introduce new active ingredients gradually, one at a time"
  ]
}"""

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
    prompt = f"""{SYSTEM_PROMPT}

User Profile:
- Skin Type: {skin_type}
- Skin Concerns: {skin_concerns}
- Budget: {budget}

Generate a complete, personalized skincare routine with product recommendations suitable for Indonesia market."""

    payload = {
        "token": Config.LLM_TOKEN,
        "chat": prompt
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
