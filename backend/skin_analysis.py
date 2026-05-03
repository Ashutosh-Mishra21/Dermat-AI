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
from typing import Optional, Dict, Any, List

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
    {"name": "string (e.g. 'Niacinamide 10%')", "concentration": "string", "format": "string (Serum/Cream/Toner/etc.)", "moa": "string (brief mechanism of action)", "targetConcern": "string (the concern this addresses, e.g. 'acne')"}
  ],
  "contraindications": "string (important warnings, pregnancy/combinations/SPF)",
  "amRoutine": [
    {"step": "string (e.g. '1. Gentle Cleanser')", "product": "string (type/description, not brand)", "note": "string (usage tip)"}
  ],
  "pmRoutine": [
    {"step": "string", "product": "string", "note": "string"}
  ],
  "incompatibilities": ["string", "string"],
  "productMatches": [
    {"query": "string — Amazon.in search query for one specific product", "matchedActive": "string — the active ingredient or routine step this product fulfills", "targetConcern": "string — which user concern this addresses", "category": "string — one of: 'cleanser'|'serum'|'moisturizer'|'sunscreen'|'treatment'|'toner'", "tier": "string — 'affordable'|'mid'|'luxury'"}
  ]
}

CRITICAL RULES for productMatches:
- Generate EXACTLY ONE product query per recommended active (one-to-one mapping with the `actives` array).
- Plus add 3 essentials: a gentle cleanser, a non-comedogenic moisturizer, and a broad-spectrum SPF 50+ sunscreen.
- Total: typically 7-10 entries.
- Use brands available on Amazon India: Minimalist, The Derma Co, Dot & Key, Plum, Mamaearth, Foxtale, The Ordinary, CeraVe, La Roche-Posay, Differin, Neutrogena, Cetaphil, EltaMD, Re'equil, Pilgrim, Deconstruct.
- Each query must contain the active ingredient name + concentration (e.g., "Minimalist Niacinamide 10% Zinc serum").
- `matchedActive` must mirror the corresponding entry in `actives` (or 'Cleanser', 'Moisturizer', 'Sunscreen' for essentials).
- `targetConcern` must come from the user's concerns list (or 'general care' for essentials).

Other rules:
- Output ONLY the JSON object. No markdown fences. No commentary.
- Consider pregnancy/breastfeeding — avoid retinoids if pregnant; prefer azelaic acid + niacinamide.
- Fitzpatrick III-VI: prioritize tyrosinase-inhibiting PIH ingredients (niacinamide, azelaic acid, alpha arbutin, tranexamic acid).
- Always include SPF 50+ in AM routine."""


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
             "moa": "Regulates sebum, reduces PIH, strengthens barrier",
             "targetConcern": "acne"},
            {"name": "Salicylic Acid 2%", "concentration": "2%", "format": "Toner",
             "moa": "Oil-soluble BHA that unclogs pores",
             "targetConcern": "acne"},
            {"name": "Azelaic Acid 10%", "concentration": "10%", "format": "Gel",
             "moa": "Antibacterial, tyrosinase inhibitor",
             "targetConcern": "pigmentation"},
            {"name": "Retinol 0.025%", "concentration": "0.025%", "format": "Night serum",
             "moa": "Cell turnover, stimulates collagen",
             "targetConcern": "wrinkles"},
            {"name": "Hyaluronic Acid", "concentration": "Multi-weight", "format": "Serum",
             "moa": "Humectant binding 1000x water for hydration",
             "targetConcern": "dehydration"},
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
            "Minimalist Niacinamide 10% Zinc serum",
            "Minimalist Salicylic Acid 2% toner",
            "The Derma Co 10% Azelaic Acid serum",
            "Minimalist Retinol 0.3% night serum",
            "The Derma Co Hyaluronic Acid serum",
            "Cetaphil Gentle Skin Cleanser",
            "CeraVe Moisturising Cream",
            "Re'equil Oxybenzone OMC Free Sunscreen SPF 50",
        ],
        "productMatches": [
            {"query": "Minimalist Niacinamide 10% Zinc serum", "matchedActive": "Niacinamide 10%", "targetConcern": "acne", "category": "serum", "tier": "affordable"},
            {"query": "Minimalist Salicylic Acid 2% toner", "matchedActive": "Salicylic Acid 2%", "targetConcern": "acne", "category": "toner", "tier": "affordable"},
            {"query": "The Derma Co 10% Azelaic Acid serum", "matchedActive": "Azelaic Acid 10%", "targetConcern": "pigmentation", "category": "treatment", "tier": "affordable"},
            {"query": "Minimalist Retinol 0.3% night serum", "matchedActive": "Retinol 0.025%", "targetConcern": "wrinkles", "category": "serum", "tier": "affordable"},
            {"query": "The Derma Co Hyaluronic Acid serum", "matchedActive": "Hyaluronic Acid", "targetConcern": "dehydration", "category": "serum", "tier": "affordable"},
            {"query": "Cetaphil Gentle Skin Cleanser", "matchedActive": "Cleanser", "targetConcern": "general care", "category": "cleanser", "tier": "affordable"},
            {"query": "CeraVe Moisturising Cream", "matchedActive": "Moisturizer", "targetConcern": "general care", "category": "moisturizer", "tier": "affordable"},
            {"query": "Re'equil Oxybenzone OMC Free Sunscreen SPF 50", "matchedActive": "Sunscreen SPF 50+", "targetConcern": "uv protection", "category": "sunscreen", "tier": "mid"},
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
            return _ensure_relevance(result, quiz)
        logger.warning("Gemini vision failed, falling back to SiliconFlow (text only)")

    # Primary: SiliconFlow (text)
    result = await _call_siliconflow(user_msg)
    if result:
        result["_source"] = "siliconflow-gpt-oss"
        return _ensure_relevance(result, quiz)

    # Fallback: OpenRouter text
    result = await _call_openrouter(user_msg, image_base64=None)
    if result:
        result["_source"] = "openrouter-gemini"
        return _ensure_relevance(result, quiz)

    # Final fallback: static response
    return _fallback_response(quiz)


# ---------- Post-processing: guarantee product relevance ----------

# Map active ingredient keywords → preferred Amazon India brand search query templates
_ACTIVE_BRAND_TEMPLATES = {
    "niacinamide": "Minimalist Niacinamide 10% Zinc serum",
    "salicylic": "Minimalist Salicylic Acid 2% toner",
    "salicylic acid": "Minimalist Salicylic Acid 2% toner",
    "bha": "Minimalist Salicylic Acid 2% BHA",
    "azelaic": "The Derma Co 10% Azelaic Acid serum",
    "retinol": "Minimalist Retinol 0.3% serum",
    "retinoid": "Minimalist Retinol 0.3% serum",
    "adapalene": "Differin Adapalene Gel 0.1%",
    "hyaluronic": "The Derma Co Hyaluronic Acid serum",
    "vitamin c": "Dot & Key Vitamin C 10% serum",
    "ascorbic": "Dot & Key Vitamin C serum",
    "ferulic": "Foxtale Vitamin C 15% serum",
    "alpha arbutin": "The Ordinary Alpha Arbutin 2% serum",
    "tranexamic": "The Derma Co Tranexamic Acid serum",
    "kojic": "Plum Kojic Acid serum",
    "glycolic": "The Ordinary Glycolic Acid 7% Toning Solution",
    "lactic": "The Ordinary Lactic Acid 10% serum",
    "aha": "Minimalist 10% AHA serum",
    "peptide": "The Ordinary Argireline Peptide solution",
    "ceramide": "Cetaphil Moisturizing Cream ceramide",
    "centella": "Pilgrim Centella Asiatica face serum",
    "tea tree": "Plum Tea Tree skin clarifying serum",
    "zinc": "Minimalist Niacinamide 10% Zinc",
    "benzoyl": "Persol Benzoyl Peroxide 2.5% gel",
    "alpha hydroxy": "Minimalist 10% AHA serum",
}

_ESSENTIALS = [
    {
        "matchers": ["cleanser", "face wash"],
        "default": {
            "query": "Cetaphil Gentle Skin Cleanser face wash",
            "matchedActive": "Cleanser",
            "targetConcern": "general care",
            "category": "cleanser",
            "tier": "affordable",
        },
    },
    {
        "matchers": ["moisturiz", "moisturis", "cream", "lotion"],
        "default": {
            "query": "CeraVe Moisturising Cream",
            "matchedActive": "Moisturizer",
            "targetConcern": "general care",
            "category": "moisturizer",
            "tier": "affordable",
        },
    },
    {
        "matchers": ["sunscreen", "spf", "sun protect"],
        "default": {
            "query": "Re'equil Oxybenzone OMC Free Sunscreen SPF 50",
            "matchedActive": "Sunscreen SPF 50+",
            "targetConcern": "uv protection",
            "category": "sunscreen",
            "tier": "mid",
        },
    },
]


def _query_for_active(active_name: str) -> str:
    """Pick a relevant Amazon India search query for a recommended active."""
    if not active_name:
        return ""
    name_low = active_name.lower()
    for keyword, template in _ACTIVE_BRAND_TEMPLATES.items():
        if keyword in name_low:
            return template
    # Generic fallback: use the active name with "serum" suffix
    return f"{active_name} serum"


def _ensure_relevance(result: Dict[str, Any], quiz: Dict[str, Any]) -> Dict[str, Any]:
    """
    Post-process the AI response so the products page always shows relevant items:
      1. Build productMatches from each recommended active (1:1 mapping).
      2. Augment with cleanser, moisturizer, sunscreen essentials if missing.
      3. Keep the AI's productMatches if present, but supplement gaps.
      4. Backwards-compat: also publish productQueries (flat list of search strings).
    """
    if not isinstance(result, dict):
        return result

    actives = result.get("actives") or []
    concerns = quiz.get("concerns") or []
    primary_concern = concerns[0] if concerns else "general care"

    existing_matches = result.get("productMatches") or []
    # Normalize existing entries (drop any without a query string)
    matches: List[Dict[str, Any]] = []
    seen_queries = set()
    for m in existing_matches:
        if not isinstance(m, dict):
            continue
        q = (m.get("query") or "").strip()
        if not q or q.lower() in seen_queries:
            continue
        seen_queries.add(q.lower())
        matches.append({
            "query": q,
            "matchedActive": m.get("matchedActive") or m.get("matched_active") or "",
            "targetConcern": m.get("targetConcern") or m.get("target_concern") or primary_concern,
            "category": (m.get("category") or "treatment").lower(),
            "tier": (m.get("tier") or "affordable").lower(),
        })

    # Ensure every recommended active has at least one matching product
    matched_active_names = {m["matchedActive"].lower() for m in matches if m.get("matchedActive")}
    for active in actives:
        if not isinstance(active, dict):
            continue
        a_name = (active.get("name") or "").strip()
        if not a_name:
            continue
        if a_name.lower() in matched_active_names:
            continue
        # Build a dedicated search for this active
        q = _query_for_active(a_name)
        if not q or q.lower() in seen_queries:
            continue
        seen_queries.add(q.lower())
        matches.append({
            "query": q,
            "matchedActive": a_name,
            "targetConcern": active.get("targetConcern") or primary_concern,
            "category": "serum",
            "tier": "affordable",
        })
        matched_active_names.add(a_name.lower())

    # Ensure essentials (cleanser, moisturizer, sunscreen) are present
    existing_blob = " ".join(
        (m.get("query", "") + " " + m.get("category", "") + " " + m.get("matchedActive", ""))
        for m in matches
    ).lower()
    for essential in _ESSENTIALS:
        if any(kw in existing_blob for kw in essential["matchers"]):
            continue
        item = essential["default"]
        if item["query"].lower() in seen_queries:
            continue
        seen_queries.add(item["query"].lower())
        matches.append(dict(item))

    # Cap to a sensible number
    matches = matches[:12]

    result["productMatches"] = matches
    # Backwards-compat: maintain a flat productQueries list (frontend uses both)
    result["productQueries"] = [m["query"] for m in matches]
    return result
