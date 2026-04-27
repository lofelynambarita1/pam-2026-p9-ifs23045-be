import logging
import requests
import json
import re
from config import Config

logger = logging.getLogger(__name__)

# Strict limits to keep output short and prevent truncation
SYSTEM_PROMPT = (
    'Reply ONLY valid JSON, no markdown. Keep all text very short (max 10 words each).\n'
    'Strict limits: morning_routine=3 steps, evening_routine=3 steps, '
    'product_recommendations=2 items, tips=2 items.\n'
    '{"routine_title":"...","summary":"...","morning_routine":[{"step":1,"name":"","product_type":"","instruction":"","why":""}],'
    '"evening_routine":[{"step":1,"name":"","product_type":"","instruction":"","why":""}],'
    '"product_recommendations":[{"category":"","product_name":"","brand":"","price_range":"","why_recommended":""}],'
    '"tips":["",""]}'
)

REQUIRED_KEYS = {"routine_title", "summary", "morning_routine", "evening_routine", "product_recommendations", "tips"}


def _try_recover_json(raw: str) -> dict:
    """Attempt to recover truncated JSON by closing open structures."""
    content = raw.strip()

    # Count open braces/brackets to figure out what needs closing
    depth_brace = content.count('{') - content.count('}')
    depth_bracket = content.count('[') - content.count(']')

    # Remove trailing incomplete key-value (e.g., "instruction": "Cuci muka dengan)
    # Find last complete value — cut at last closing } or ]
    last_safe = max(content.rfind('}'), content.rfind('"'))
    if last_safe > 0 and content[last_safe] == '"':
        # We're mid-string — cut before this string started
        # Find the last comma before this incomplete entry
        cut = content.rfind(',', 0, last_safe - 50)
        if cut > 0:
            content = content[:cut]
            # Recount
            depth_brace = content.count('{') - content.count('}')
            depth_bracket = content.count('[') - content.count(']')

    # Close open arrays then objects
    content += ']' * depth_bracket + '}' * depth_brace

    return json.loads(content)


def _validate_result(result: dict) -> dict:
    missing = REQUIRED_KEYS - result.keys()
    if missing:
        raise ValueError(f"Missing keys: {missing}")

    result["routine_title"] = str(result["routine_title"]).strip() or "Personalized Skincare Routine"
    result["summary"] = str(result["summary"]).strip()

    for key in ["morning_routine", "evening_routine", "product_recommendations", "tips"]:
        if not isinstance(result[key], list):
            result[key] = []

    return result


def generate_skincare_routine(skin_type: str, skin_concerns: str, budget: str) -> dict:
    prompt = (
        f"{SYSTEM_PROMPT}\n"
        f"Skin:{skin_type}, Issues:{skin_concerns[:80]}, Budget:{budget}, Market:Indonesia."
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
        logger.warning("LLM returned truncated JSON, attempting recovery: %s", e)
        try:
            result = _try_recover_json(content)
            logger.info("JSON recovery successful")
        except Exception as e2:
            logger.error("JSON recovery failed: %s | raw: %s", e2, content[:300])
            raise ValueError("LLM returned invalid JSON") from e

    return _validate_result(result)