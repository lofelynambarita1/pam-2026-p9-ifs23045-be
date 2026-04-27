import logging
import requests
import json
from config import Config

logger = logging.getLogger(__name__)

# Ultra-compact schema to minimize input tokens
SYSTEM_PROMPT = 'Reply ONLY valid JSON: {"routine_title":"","summary":"","morning_routine":[{"step":1,"name":"","product_type":"","instruction":"","why":""}],"evening_routine":[{"step":1,"name":"","product_type":"","instruction":"","why":""}],"product_recommendations":[{"category":"","product_name":"","brand":"","price_range":"","why_recommended":""}],"tips":[""]}'

REQUIRED_KEYS = {"routine_title", "summary", "morning_routine", "evening_routine", "product_recommendations", "tips"}


def _validate_result(result: dict) -> dict:
    missing = REQUIRED_KEYS - result.keys()
    if missing:
        raise ValueError(f"Missing keys: {missing}")

    result["routine_title"] = str(result["routine_title"]).strip() or "Personalized Skincare Routine"
    result["summary"] = str(result["summary"]).strip()

    for key in ["morning_routine", "evening_routine", "product_recommendations", "tips"]:
        if not isinstance(result[key], list):
            raise ValueError(f"{key} must be a list")

    return result


def generate_skincare_routine(skin_type: str, skin_concerns: str, budget: str) -> dict:
    prompt = (
        f"{SYSTEM_PROMPT}\n"
        f"Skincare routine. Skin:{skin_type}, Issues:{skin_concerns}, Budget:{budget}, Market:Indonesia."
    )

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
# NOTE: Tambahkan batasan jumlah item di prompt jika kredit masih kurang:
# f"...Keep: 3 morning steps, 3 evening steps, 3 products, 3 tips max."