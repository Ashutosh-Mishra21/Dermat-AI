"""
Amazon product data via OpenWeb Ninja (direct API, not RapidAPI).
Fetches real-time Indian Rupee prices + product URLs for Amazon.in.

Docs: https://www.openwebninja.com/api/real-time-amazon-data
Base:  https://api.openwebninja.com/realtime-amazon-data
Auth:  X-API-KEY header
"""

import os
import logging
import httpx
from typing import List, Dict, Any, Optional
import asyncio

logger = logging.getLogger(__name__)

BASE_URL = "https://api.openwebninja.com/realtime-amazon-data"


def _headers() -> Optional[Dict[str, str]]:
    api_key = os.environ.get("OPENWEB_NINJA_API_KEY", "").strip()
    if not api_key:
        return None
    return {
        "x-api-key": api_key,
        "Accept": "application/json",
    }


def _tier_from_price(price_inr: Optional[float]) -> str:
    """Classify price tier (INR)."""
    if price_inr is None:
        return "mid"
    if price_inr < 1500:
        return "affordable"
    if price_inr < 5000:
        return "mid"
    return "luxury"


def _tier_label(tier: str) -> str:
    return {"affordable": "Affordable", "mid": "Mid-range", "luxury": "Luxury"}.get(
        tier, "Mid-range"
    )


def _icon_for_query(q: str) -> str:
    ql = q.lower()
    if "niacinamide" in ql:
        return "🧴"
    if "salicylic" in ql or "bha" in ql:
        return "🫙"
    if "vitamin c" in ql:
        return "💛"
    if "retinol" in ql or "adapalene" in ql or "retinoid" in ql:
        return "💊"
    if "moisturiz" in ql or "moisturis" in ql or "cream" in ql or "ceramide" in ql:
        return "🤍"
    if "sunscreen" in ql or "spf" in ql or "sun " in ql:
        return "🌤️"
    if "hyaluronic" in ql:
        return "💧"
    if "azelaic" in ql:
        return "🌿"
    if "aha" in ql or "glycolic" in ql or "lactic" in ql:
        return "🔵"
    return "✨"


def _parse_price(price_str: Optional[str]) -> Optional[float]:
    if not price_str:
        return None
    try:
        # Strip ₹, commas, whitespace
        cleaned = "".join(c for c in str(price_str) if c.isdigit() or c == ".")
        if not cleaned:
            return None
        return float(cleaned)
    except Exception:
        return None


def _format_inr(value: Optional[float]) -> str:
    if value is None:
        return "—"
    # Indian number formatting (lakh/crore style)
    try:
        v = int(round(value))
        s = str(v)
        if len(s) <= 3:
            return f"₹{s}"
        last3 = s[-3:]
        rest = s[:-3]
        parts = []
        while len(rest) > 2:
            parts.append(rest[-2:])
            rest = rest[:-2]
        if rest:
            parts.append(rest)
        formatted = ",".join(reversed(parts)) + "," + last3
        return f"₹{formatted}"
    except Exception:
        return f"₹{value}"


async def _search_one(
    client: httpx.AsyncClient,
    headers: Dict[str, str],
    match: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Fetch the top Amazon.in product for a query, preserving match metadata."""
    query = match.get("query") or ""
    if not query:
        return None
    params = {
        "query": query,
        "page": "1",
        "country": "IN",
        "sort_by": "RELEVANCE",
        "product_condition": "NEW",
    }
    try:
        r = await client.get(
            f"{BASE_URL}/search", headers=headers, params=params, timeout=25.0
        )
        if r.status_code != 200:
            logger.warning(
                f"Amazon search failed [{r.status_code}] for '{query}': {r.text[:150]}"
            )
            return None
        data = r.json()
        products = (data.get("data") or {}).get("products") or []
        if not products:
            return None
        # Take first item
        p = products[0]
        price_raw = p.get("product_price") or p.get("product_original_price")
        price_val = _parse_price(price_raw)
        original_raw = p.get("product_original_price")
        url = p.get("product_url") or ""
        asin = p.get("asin")
        if not url and asin:
            url = f"https://www.amazon.in/dp/{asin}"

        # If AI suggested a tier, prefer it; otherwise derive from live price
        tier = (match.get("tier") or "").lower() or _tier_from_price(price_val)
        actives_raw = p.get("product_title", "")
        return {
            "query": query,
            "name": p.get("product_title") or query,
            "brand": (actives_raw.split()[0] if actives_raw else "Amazon"),
            "price": _format_inr(price_val) if price_val else (price_raw or "—"),
            "priceValue": price_val,
            "originalPrice": original_raw,
            "rating": p.get("product_star_rating"),
            "reviews": p.get("product_num_ratings"),
            "image": p.get("product_photo"),
            "url": url,
            "asin": asin,
            "tier": tier,
            "tierlabel": _tier_label(tier),
            "icon": _icon_for_query(query),
            "badge": "Prime" if p.get("is_prime") else "Amazon.in",
            # Relevance metadata — drives "For: <ingredient>" labels and concern filters
            "matchedActive": match.get("matchedActive") or "",
            "targetConcern": match.get("targetConcern") or "",
            "category": match.get("category") or "",
        }
    except Exception as e:
        logger.warning(f"Amazon search error for '{query}': {e}")
        return None


async def search_products(matches: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Run parallel Amazon.in searches across rich match objects.

    Each match is a dict with at least {"query": str} and optional metadata
    (matchedActive, targetConcern, category, tier).
    """
    headers = _headers()
    if not headers:
        logger.info("OpenWeb Ninja API key not set — returning empty list")
        return []

    # Backwards-compat: accept plain strings too
    norm: List[Dict[str, Any]] = []
    for m in matches:
        if isinstance(m, str):
            norm.append({"query": m})
        elif isinstance(m, dict):
            norm.append(m)

    async with httpx.AsyncClient() as client:
        tasks = [_search_one(client, headers, m) for m in norm]
        results = await asyncio.gather(*tasks, return_exceptions=False)
    return [r for r in results if r]


# Curated India-popular skincare queries for the "All Bestsellers" view.
# These are chosen to cover the common concerns shoppers care about.
_BESTSELLER_QUERIES: List[Dict[str, Any]] = [
    {"query": "Minimalist Niacinamide 10% serum", "matchedActive": "Niacinamide 10%", "targetConcern": "acne", "category": "serum"},
    {"query": "Minimalist Salicylic Acid 2% BHA toner", "matchedActive": "Salicylic Acid 2%", "targetConcern": "acne", "category": "toner"},
    {"query": "The Derma Co 10% Vitamin C serum", "matchedActive": "Vitamin C 10%", "targetConcern": "pigmentation", "category": "serum"},
    {"query": "The Derma Co Hyaluronic Acid serum", "matchedActive": "Hyaluronic Acid", "targetConcern": "hydration", "category": "serum"},
    {"query": "Dot & Key Vitamin C E serum", "matchedActive": "Vitamin C + E", "targetConcern": "pigmentation", "category": "serum"},
    {"query": "Plum Green Tea face wash", "matchedActive": "Cleanser", "targetConcern": "general care", "category": "cleanser"},
    {"query": "Cetaphil Gentle Skin Cleanser", "matchedActive": "Cleanser", "targetConcern": "general care", "category": "cleanser"},
    {"query": "CeraVe Moisturising Cream", "matchedActive": "Moisturizer", "targetConcern": "general care", "category": "moisturizer"},
    {"query": "Foxtale Daily Hydrating moisturizer", "matchedActive": "Moisturizer", "targetConcern": "hydration", "category": "moisturizer"},
    {"query": "Re'equil Sunscreen SPF 50", "matchedActive": "Sunscreen SPF 50", "targetConcern": "uv protection", "category": "sunscreen"},
    {"query": "Minimalist Sunscreen SPF 50 Multi-Vitamins", "matchedActive": "Sunscreen SPF 50", "targetConcern": "uv protection", "category": "sunscreen"},
    {"query": "Minimalist Retinol 0.3% serum", "matchedActive": "Retinol 0.3%", "targetConcern": "aging", "category": "serum"},
]


async def get_bestsellers() -> List[Dict[str, Any]]:
    """Return a curated list of popular India skincare products with live prices."""
    return await search_products(_BESTSELLER_QUERIES)
