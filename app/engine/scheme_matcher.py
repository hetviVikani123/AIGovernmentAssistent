"""
Scheme Matching Engine — filters government schemes based on user profile.

This is the deterministic core: no LLM involved, pure rule-based matching.
"""

import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_SCHEMES_PATH = Path(__file__).resolve().parent.parent / "data" / "schemes.json"
_schemes_cache: Optional[list] = None


def _load_schemes() -> list:
    """Load schemes from JSON file (cached after first read)."""
    global _schemes_cache
    if _schemes_cache is None:
        with open(_SCHEMES_PATH, "r", encoding="utf-8") as f:
            _schemes_cache = json.load(f)
        logger.info("Loaded %d schemes from dataset", len(_schemes_cache))
    return _schemes_cache


def get_all_schemes() -> list:
    """Return all schemes."""
    return _load_schemes()


def get_scheme_by_id(scheme_id: str) -> Optional[dict]:
    """Look up a single scheme by its ID."""
    for s in _load_schemes():
        if s["id"] == scheme_id:
            return s
    return None


def match_schemes(
    category: Optional[str] = None,
    income_value: Optional[int] = None,
    state_name: Optional[str] = None,
    special_category: Optional[str] = None,
) -> list[dict]:
    """
    Match schemes against user profile.

    Matching rules (AND logic — a scheme must pass ALL applicable filters):
    1. Category: scheme's category list must include the user's category
    2. Income: if scheme has max_income, user's income must be ≤ that threshold
    3. State: if scheme is state-specific, must match user's state (currently all are 'all')
    4. Special category: if scheme requires a special category, user must have it
       (schemes without special_category requirement are open to everyone)
    """
    schemes = _load_schemes()
    results = []

    for scheme in schemes:
        elig = scheme.get("eligibility", {})

        # --- Category filter ---
        if category and category not in scheme.get("category", []):
            continue

        # --- Income filter ---
        max_income = elig.get("max_income")
        if max_income is not None and income_value is not None:
            if income_value > max_income:
                continue

        # --- State filter ---
        scheme_states = elig.get("states", "all")
        if scheme_states != "all" and state_name:
            if state_name.lower() not in [s.lower() for s in scheme_states]:
                continue

        # --- Special category filter ---
        # If the scheme requires a special category, only match if user has it
        scheme_special = elig.get("special_category")
        if scheme_special is not None:
            if special_category is None or special_category != scheme_special:
                continue

        results.append(scheme)

    logger.info(
        "Matched %d schemes for category=%s, income=%s, state=%s, special=%s",
        len(results), category, income_value, state_name, special_category,
    )
    return results


def format_scheme_summary(scheme: dict) -> str:
    """Format a single scheme for WhatsApp display."""
    return (
        f"✅ *{scheme['name']}*\n"
        f"💰 Benefit: {scheme['benefits']}\n"
        f"👤 Who can apply: {scheme['eligibility']['description']}\n"
        f"📄 Documents needed: {', '.join(scheme['documents'][:3])}..."
    )


def format_scheme_detail(scheme: dict) -> str:
    """Format full scheme detail with step-by-step application guide."""
    docs = "\n".join(f"  • {d}" for d in scheme["documents"])
    steps = "\n".join(f"  {i+1}. {s}" for i, s in enumerate(scheme["how_to_apply"]))

    return (
        f"📋 *{scheme['name']}*\n\n"
        f"💰 *Benefit:*\n{scheme['benefits']}\n\n"
        f"👤 *Eligibility:*\n{scheme['eligibility']['description']}\n\n"
        f"📄 *Documents Required:*\n{docs}\n\n"
        f"📝 *How to Apply (Step by Step):*\n{steps}\n\n"
        f"🔗 Apply here: {scheme['application_url']}"
    )
