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
    client: httpx.AsyncClient, headers: Dict[str, str], query: str
) -> Optional[Dict[str, Any]]:
    """Fetch the top Amazon.in product for a query."""
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
            logger.warning(f"Amazon search failed [{r.status_code}] for '{query}': {r.text[:150]}")
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
        # Build affiliate-less direct URL with ASIN if needed
        asin = p.get("asin")
        if not url and asin:
            url = f"https://www.amazon.in/dp/{asin}"
        tier = _tier_from_price(price_val)
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
        }
    except Exception as e:
        logger.warning(f"Amazon search error for '{query}': {e}")
        return None


async def search_products(queries: List[str]) -> List[Dict[str, Any]]:
    """Run parallel searches across multiple product queries (Amazon.in)."""
    headers = _headers()
    if not headers:
        logger.info("OpenWeb Ninja API key not set — returning empty list")
        return []
    async with httpx.AsyncClient() as client:
        tasks = [_search_one(client, headers, q) for q in queries]
        results = await asyncio.gather(*tasks, return_exceptions=False)
    return [r for r in results if r]
