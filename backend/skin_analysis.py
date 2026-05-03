"""
AI skin analysis service.
Primary: SiliconFlow (GPT OSS 120B) - text-only
Fallback: OpenRouter (Gemini 2.5 Flash) - supports vision

If a photo is provided, Gemini is used directly (vision required).
"""

import os
import json
import logging
import httpx
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

SILICONFLOW_URL = "https://api.siliconflow.com/v1/chat/completions"
SILICONFLOW_MODEL = "openai/gpt-oss-120b"

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODEL = "google/gemini-2.5-flash"

SYSTEM_PROMPT = """You are DermaSense AI, a dermatology-trained assistant providing evidence-based skincare guidance. You produce clinically-informed, educational responses. Not a replacement for a board-certified dermatologist.

Given a user's quiz responses (and optionally a skin photo), produce a STRICT JSON object with this exact shape:

{
  "skinType": "string (e.g. 'Oily / Acne-prone')",
  "fitzpatrick": "string (e.g. 'Type III')",
  "primaryConcern": "string (e.g. 'Acne + Pigmentation')",
  "severity": "string ('Mild'|'Moderate'|'Severe')",
  "uvRisk": "string ('Low'|'Moderate'|'High'|'Very High')",
  "photoInsights": "string or null — short clinical observations from the photo if provided (else null)",
  "actives": [
    {"name": "string (e.g. 'Niacinamide 10%')", "concentration": "string", "format": "string (Serum/Cream/Toner/etc.)", "moa": "string (brief mechanism of action)"}
  ],
  "contraindications": "string (important warnings, pregnancy/combinations/SPF)",
  "amRoutine": [
    {"step": "string (e.g. '1. Gentle Cleanser')", "product": "string (type/description, not brand)", "note": "string (usage tip)"}
  ],
  "pmRoutine": [
    {"step": "string", "product": "string", "note": "string"}
  ],
  "incompatibilities": ["string", "string"],
  "productQueries": ["string — 6 to 9 precise Amazon search queries for matching products across affordable/mid/luxury tiers, e.g. 'The Ordinary Niacinamide 10% Zinc 1%'"]
}

Rules:
- Output ONLY the JSON object. No markdown fences. No commentary.
- Consider pregnancy/breastfeeding status — avoid retinoids if pregnant.
- Fitzpatrick III-VI: prioritize tyrosinase-inhibiting PIH ingredients.
- Always include SPF 50+ in AM routine.
- productQueries should be searchable on Amazon India."""


def _build_user_message(quiz: Dict[str, Any]) -> str:
    lines = ["User quiz responses:"]
    lines.append(f"- Skin type: {quiz.get('skintype') or 'not specified'}")
    lines.append(f"- Fitzpatrick: Type {quiz.get('fitz') or 'not specified'}")
    concerns = quiz.get("concerns") or []
    lines.append(f"- Concerns: {', '.join(concerns) if concerns else 'none'}")
    lines.append(f"- Severity: {quiz.get('severity') or 'moderate'}")
    lines.append(f"- Sun exposure: {quiz.get('sun') or 'moderate'}")
    lines.append(f"- Sleep (hrs): {quiz.get('sleep') or 7}")
    lines.append(f"- Stress: {quiz.get('stress') or 'moderate'}")
    lines.append(f"- Diet: {quiz.get('diet') or 'balanced'}")
    lines.append(f"- Current cleanser: {quiz.get('cleanser') or 'none specified'}")
    actives = quiz.get("currentActives") or []
    lines.append(f"- Currently using actives: {', '.join(actives) if actives else 'none'}")
    lines.append(f"- Allergies/sensitivities: {quiz.get('allergies') or 'none reported'}")
    lines.append(f"- Pregnancy status: {quiz.get('pregnancy') or 'no'}")
    return "\n".join(lines)


def _extract_json(text: str) -> Dict[str, Any]:
    """Extract JSON from LLM output, even if wrapped in code fences."""
    text = text.strip()
    if text.startswith("```"):
        # strip ``` or ```json fence
        first_nl = text.find("\n")
        if first_nl != -1:
            text = text[first_nl + 1 :]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
    # Find first `{` and last `}` to be safe
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        text = text[start : end + 1]
    return json.loads(text)


async def _call_siliconflow(user_msg: str) -> Optional[Dict[str, Any]]:
    api_key = os.environ.get("SILICONFLOW_API_KEY", "").strip()
    if not api_key:
        logger.info("SiliconFlow API key not set — skipping")
        return None

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": SILICONFLOW_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
        "temperature": 0.4,
        "max_tokens": 2000,
        "response_format": {"type": "json_object"},
    }
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            r = await client.post(SILICONFLOW_URL, headers=headers, json=payload)
            r.raise_for_status()
            data = r.json()
            content = data["choices"][0]["message"]["content"]
            return _extract_json(content)
    except Exception as e:
        logger.warning(f"SiliconFlow call failed: {e}")
        return None


async def _call_openrouter(
    user_msg: str, image_base64: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        logger.info("OpenRouter API key not set — skipping")
        return None

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://dermasense.ai",
        "X-Title": "DermaSense AI",
    }

    if image_base64:
        user_content = [
            {"type": "text", "text": user_msg},
            {
                "type": "image_url",
                "image_url": {"url": image_base64},
            },
        ]
    else:
        user_content = user_msg

    payload = {
        "model": OPENROUTER_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        "temperature": 0.4,
        "max_tokens": 2000,
    }
    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            r = await client.post(OPENROUTER_URL, headers=headers, json=payload)
            r.raise_for_status()
            data = r.json()
            content = data["choices"][0]["message"]["content"]
            return _extract_json(content)
    except Exception as e:
        logger.warning(f"OpenRouter call failed: {e}")
        return None


def _fallback_response(quiz: Dict[str, Any]) -> Dict[str, Any]:
    """Static default so UI still works when no API keys are set."""
    concerns = quiz.get("concerns") or ["acne", "pigmentation"]
    primary = " + ".join(c.capitalize() for c in concerns[:2]) or "Acne + Pigmentation"
    return {
        "skinType": (quiz.get("skintype") or "Combination").capitalize(),
        "fitzpatrick": f"Type {quiz.get('fitz') or 'III'}",
        "primaryConcern": primary,
        "severity": (quiz.get("severity") or "Moderate").capitalize(),
        "uvRisk": "Moderate",
        "photoInsights": None,
        "actives": [
            {"name": "Niacinamide 10%", "concentration": "10%", "format": "Serum",
             "moa": "Regulates sebum, reduces PIH, strengthens barrier"},
            {"name": "Salicylic Acid 2%", "concentration": "2%", "format": "Toner",
             "moa": "Oil-soluble BHA that unclogs pores"},
            {"name": "Azelaic Acid 10%", "concentration": "10%", "format": "Gel",
             "moa": "Antibacterial, tyrosinase inhibitor"},
            {"name": "Retinol 0.025%", "concentration": "0.025%", "format": "Night serum",
             "moa": "Cell turnover, stimulates collagen"},
            {"name": "Hyaluronic Acid", "concentration": "Multi-weight", "format": "Serum",
             "moa": "Humectant binding 1000x water for hydration"},
        ],
        "contraindications": "Retinol must be avoided if pregnant or breastfeeding. Do not combine salicylic acid with high-concentration retinol on the same night initially. Always apply SPF 30+ in the AM when using retinoids or AHAs/BHAs.",
        "amRoutine": [
            {"step": "1. Gentle Cleanser", "product": "Low pH, non-stripping formula",
             "note": "Avoid foaming SLS cleansers — they disrupt the acid mantle."},
            {"step": "2. Niacinamide Serum", "product": "10% Niacinamide + Zinc",
             "note": "Apply to damp skin. Wait 60 sec before layering."},
            {"step": "3. Lightweight Moisturizer", "product": "Oil-free non-comedogenic gel cream",
             "note": "Hyaluronic acid base with ceramides for barrier support."},
            {"step": "4. Sunscreen SPF 50+", "product": "Broad-spectrum chemical or mineral",
             "note": "Non-negotiable. Reapply every 2 hrs outdoors."},
        ],
        "pmRoutine": [
            {"step": "1. Double Cleanse", "product": "Micellar water → gentle foaming cleanser",
             "note": "Remove sunscreen/makeup fully before actives."},
            {"step": "2. BHA Toner (3x/week)", "product": "2% Salicylic Acid",
             "note": "Alternate nights with retinol."},
            {"step": "3. Retinol (2x/week)", "product": "0.025% Retinol in moisturizing base",
             "note": "Buffer with moisturizer underneath if sensitive."},
            {"step": "4. Barrier Moisturizer", "product": "Ceramide + peptide cream",
             "note": "Lock in actives and support overnight repair."},
        ],
        "incompatibilities": [
            "Do not layer Vitamin C + Niacinamide at high concentrations — may cause temporary flushing. Use AM/PM split instead.",
            "Avoid Retinol and high-strength AHA/BHA on the same evening until skin is acclimatized (4-6 weeks).",
        ],
        "productQueries": [
            "The Ordinary Niacinamide 10% Zinc 1%",
            "Paula's Choice BHA 2% Liquid Exfoliant",
            "CeraVe Moisturising Cream",
            "Differin Adapalene Gel 0.1%",
            "Minimalist Niacinamide 10% serum",
            "La Roche-Posay Effaclar Duo",
            "The Derma Co Hyaluronic Acid serum",
            "Dot & Key Vitamin C serum",
            "Neutrogena UltraSheer SPF 50",
        ],
        "_source": "fallback",
    }


async def analyze_skin(
    quiz: Dict[str, Any], image_base64: Optional[str] = None
) -> Dict[str, Any]:
    """Run skin analysis with SiliconFlow primary, OpenRouter fallback."""
    user_msg = _build_user_message(quiz)

    # If photo provided, vision is required → use OpenRouter (Gemini) directly
    if image_base64:
        result = await _call_openrouter(user_msg, image_base64=image_base64)
        if result:
            result["_source"] = "openrouter-gemini-vision"
            return result
        logger.warning("Gemini vision failed, falling back to SiliconFlow (text only)")

    # Primary: SiliconFlow (text)
    result = await _call_siliconflow(user_msg)
    if result:
        result["_source"] = "siliconflow-gpt-oss"
        return result

    # Fallback: OpenRouter text
    result = await _call_openrouter(user_msg, image_base64=None)
    if result:
        result["_source"] = "openrouter-gemini"
        return result

    # Final fallback: static response
    return _fallback_response(quiz)
