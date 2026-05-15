"""
Conversation State Machine — the deterministic backbone of the agent.

Controls the entire conversation flow. AI is only called for language
tasks (simplification, fallback), never for flow decisions.
"""

import logging
from typing import Optional

from app.data import store
from app.engine.models import (
    ConversationState,
    INCOME_RANGE_VALUES,
    IncomeRange,
)
from app.engine.scheme_matcher import (
    match_schemes,
    format_scheme_summary,
    format_scheme_detail,
    get_scheme_by_id,
)
from app.ai.llm import ask_llm_fallback, detect_language

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# Input normalisation maps
# ──────────────────────────────────────────────
CATEGORY_MAP = {
    "1": "student", "student": "student",
    "2": "farmer", "farmer": "farmer",
    "3": "job_seeker", "job seeker": "job_seeker", "jobseeker": "job_seeker", "job": "job_seeker",
    "4": "other", "other": "other",
}

INCOME_MAP = {
    "1": IncomeRange.BELOW_1L, "below 1 lakh": IncomeRange.BELOW_1L,
    "2": IncomeRange.L1_TO_3L, "1-3 lakh": IncomeRange.L1_TO_3L, "1 to 3 lakh": IncomeRange.L1_TO_3L,
    "3": IncomeRange.L3_TO_5L, "3-5 lakh": IncomeRange.L3_TO_5L, "3 to 5 lakh": IncomeRange.L3_TO_5L,
    "4": IncomeRange.ABOVE_5L, "above 5 lakh": IncomeRange.ABOVE_5L,
}

INDIAN_STATES = [
    "andhra pradesh", "arunachal pradesh", "assam", "bihar", "chhattisgarh",
    "goa", "gujarat", "haryana", "himachal pradesh", "jharkhand", "karnataka",
    "kerala", "madhya pradesh", "maharashtra", "manipur", "meghalaya",
    "mizoram", "nagaland", "odisha", "punjab", "rajasthan", "sikkim",
    "tamil nadu", "telangana", "tripura", "uttar pradesh", "uttarakhand",
    "west bengal", "delhi", "jammu and kashmir", "ladakh",
    "chandigarh", "puducherry", "lakshadweep",
    "dadra and nagar haveli and daman and diu", "andaman and nicobar islands",
]

SPECIAL_CATEGORY_MAP = {
    "1": None, "none": None, "no": None,
    "2": "sc_st_women", "sc/st": "sc_st_women", "sc": "sc_st_women", "st": "sc_st_women",
    "3": "girl_child", "girl child": "girl_child",
    "4": "senior_citizen", "senior citizen": "senior_citizen", "senior": "senior_citizen",
    "5": None,  # skip
}


async def handle_message(phone: str, message: str) -> str:
    """
    Main entry point: takes user phone + message text, returns bot response.

    The state machine decides what to do; AI is ONLY used for fallback / language.
    """
    message = message.strip()
    msg_lower = message.lower()

    # ── Handle reset command ──
    if msg_lower in ("reset", "restart", "start over", "/start"):
        await store.reset_user(phone)
        return await _welcome_message()

    # ── Handle greetings as conversation start/restart ──
    GREETINGS = {
        "hi", "hello", "hey", "namaste", "hii", "hiii",
        "namaskar", "good morning", "good afternoon", "good evening",
        "start", "begin", "help", "helo", "hola",
    }
    if msg_lower in GREETINGS:
        await store.reset_user(phone)
        return await _welcome_message()

    # ── Load or create user ──
    user = await store.get_user(phone)
    if user is None:
        await store.upsert_user(phone, state=ConversationState.START)
        user = await store.get_user(phone)

    state = user["state"]
    profile = user["profile"]

    # ── Detect language (lightweight) ──
    lang = await detect_language(message)
    if lang != user.get("language", "en"):
        await store.upsert_user(
            phone, state=state, profile=profile,
            matched_schemes=user["matched_schemes"],
            selected_scheme_id=user["selected_scheme_id"],
            language=lang,
        )

    # ── State-based routing ──
    if state == ConversationState.START:
        return await _handle_start(phone)

    elif state == ConversationState.CATEGORY_SELECTION:
        return await _handle_category(phone, msg_lower, profile)

    elif state == ConversationState.ASK_INCOME:
        return await _handle_income(phone, msg_lower, profile)

    elif state == ConversationState.ASK_STATE:
        return await _handle_state_name(phone, msg_lower, profile)

    elif state == ConversationState.ASK_SPECIAL_CATEGORY:
        return await _handle_special_category(phone, msg_lower, profile)

    elif state == ConversationState.SHOW_RESULTS:
        return await _handle_show_results_interaction(phone, msg_lower, user)

    elif state == ConversationState.DEEP_GUIDE:
        return await _handle_deep_guide_interaction(phone, msg_lower, user)

    elif state == ConversationState.ASK_ANOTHER:
        return await _handle_ask_another(phone, msg_lower)

    else:
        # Unknown state — reset
        await store.reset_user(phone)
        return await _welcome_message()


# ─────────────────────────────────────────────
# State handlers
# ─────────────────────────────────────────────

async def _welcome_message() -> str:
    return (
        "🙏 *Namaste!* Welcome to the Government Schemes Assistant.\n\n"
        "I can help you find government schemes you're eligible for "
        "and guide you step-by-step through the application process.\n\n"
        "Let's get started! Tell me about yourself:\n\n"
        "1️⃣ Student\n"
        "2️⃣ Farmer\n"
        "3️⃣ Job Seeker\n"
        "4️⃣ Other\n\n"
        "_Reply with a number or type your category._"
    )


async def _handle_start(phone: str) -> str:
    await store.update_user_state(phone, ConversationState.CATEGORY_SELECTION)
    return await _welcome_message()


async def _handle_category(phone: str, msg: str, profile: dict) -> str:
    category = CATEGORY_MAP.get(msg)
    if category is None:
        return (
            "🤔 Sorry, I didn't understand that.\n\n"
            "Please reply with:\n"
            "1️⃣ Student\n"
            "2️⃣ Farmer\n"
            "3️⃣ Job Seeker\n"
            "4️⃣ Other"
        )
    profile["category"] = category
    await store.update_user_profile(phone, profile)
    await store.update_user_state(phone, ConversationState.ASK_INCOME)

    category_label = category.replace("_", " ").title()
    return (
        f"👍 Great, *{category_label}*!\n\n"
        "Now, what is your family's annual income?\n\n"
        "1️⃣ Below ₹1 lakh\n"
        "2️⃣ ₹1–3 lakh\n"
        "3️⃣ ₹3–5 lakh\n"
        "4️⃣ Above ₹5 lakh\n\n"
        "_Reply with a number._"
    )


async def _handle_income(phone: str, msg: str, profile: dict) -> str:
    income_range = INCOME_MAP.get(msg)
    if income_range is None:
        return (
            "🤔 Please select your income range:\n\n"
            "1️⃣ Below ₹1 lakh\n"
            "2️⃣ ₹1–3 lakh\n"
            "3️⃣ ₹3–5 lakh\n"
            "4️⃣ Above ₹5 lakh"
        )
    profile["income_range"] = income_range.value
    profile["income_value"] = INCOME_RANGE_VALUES[income_range]
    await store.update_user_profile(phone, profile)
    await store.update_user_state(phone, ConversationState.ASK_STATE)

    return (
        "📍 Which state do you live in?\n\n"
        "_Type your state name (e.g., Maharashtra, Tamil Nadu, Delhi)_"
    )


async def _handle_state_name(phone: str, msg: str, profile: dict) -> str:
    # Fuzzy match against known states
    matched_state = None
    for s in INDIAN_STATES:
        if msg in s or s in msg:
            matched_state = s.title()
            break

    if matched_state is None:
        return (
            "🤔 I couldn't recognise that state.\n\n"
            "Please type a valid Indian state or UT name\n"
            "_(e.g., Maharashtra, Kerala, Delhi, Uttar Pradesh)_"
        )

    profile["state_name"] = matched_state
    await store.update_user_profile(phone, profile)
    await store.update_user_state(phone, ConversationState.ASK_SPECIAL_CATEGORY)

    return (
        "One more question!\n\n"
        "Do you belong to any special category?\n\n"
        "1️⃣ None / General\n"
        "2️⃣ SC / ST\n"
        "3️⃣ Girl Child (scheme beneficiary)\n"
        "4️⃣ Senior Citizen (60+)\n"
        "5️⃣ Skip\n\n"
        "_Reply with a number._"
    )


async def _handle_special_category(phone: str, msg: str, profile: dict) -> str:
    if msg not in SPECIAL_CATEGORY_MAP and msg not in ("skip", "5"):
        return (
            "🤔 Please select:\n\n"
            "1️⃣ None / General\n"
            "2️⃣ SC / ST\n"
            "3️⃣ Girl Child\n"
            "4️⃣ Senior Citizen\n"
            "5️⃣ Skip"
        )

    special = SPECIAL_CATEGORY_MAP.get(msg)
    profile["special_category"] = special
    await store.update_user_profile(phone, profile)

    # ── Run scheme matching ──
    results = match_schemes(
        category=profile.get("category"),
        income_value=profile.get("income_value"),
        state_name=profile.get("state_name"),
        special_category=special,
    )

    if not results:
        # Try without special category for broader results
        results = match_schemes(
            category=profile.get("category"),
            income_value=profile.get("income_value"),
            state_name=profile.get("state_name"),
            special_category=None,
        )

    scheme_ids = [s["id"] for s in results]
    await store.update_matched_schemes(phone, scheme_ids)
    await store.update_user_state(phone, ConversationState.SHOW_RESULTS)

    if not results:
        await store.update_user_state(phone, ConversationState.ASK_ANOTHER)
        return (
            "😔 I couldn't find any matching schemes with your current profile.\n\n"
            "This could be because:\n"
            "• Your income may be above the scheme limits\n"
            "• Schemes in your category may have specific requirements\n\n"
            "Would you like to:\n"
            "1️⃣ Try a different category\n"
            "2️⃣ Start over\n\n"
            "_Type 1 or 2_"
        )

    # ── Format results ──
    response = f"🎉 *Great news!* I found *{len(results)}* scheme(s) for you:\n\n"
    for i, scheme in enumerate(results[:5], 1):  # Show top 5
        response += f"*{i}.* {format_scheme_summary(scheme)}\n\n"

    response += (
        "────────────────\n"
        "Want detailed step-by-step guidance for any scheme?\n\n"
        f"_Reply with the scheme number (1–{min(len(results), 5)}) "
        "or type 'more' to search again._"
    )
    return response


async def _handle_show_results_interaction(phone: str, msg: str, user: dict) -> str:
    """User is viewing results and picking a scheme for detail."""
    matched_ids = user["matched_schemes"]

    if msg in ("more", "restart", "start over"):
        await store.reset_user(phone)
        return await _welcome_message()

    # Try to parse scheme number
    try:
        idx = int(msg) - 1
        if 0 <= idx < len(matched_ids):
            scheme_id = matched_ids[idx]
            scheme = get_scheme_by_id(scheme_id)
            if scheme:
                await store.update_selected_scheme(phone, scheme_id)
                await store.update_user_state(phone, ConversationState.DEEP_GUIDE)

                detail = format_scheme_detail(scheme)
                return (
                    f"{detail}\n\n"
                    "────────────────\n"
                    "What would you like to do next?\n\n"
                    "1️⃣ See another scheme\n"
                    "2️⃣ Ask a question about this scheme\n"
                    "3️⃣ Start over with a new search\n\n"
                    "_Reply with a number._"
                )
    except ValueError:
        pass

    return (
        f"🤔 Please reply with a number (1–{min(len(matched_ids), 5)}) "
        "to see scheme details, or type *more* to search again."
    )


async def _handle_deep_guide_interaction(phone: str, msg: str, user: dict) -> str:
    """User is in the deep guide state — viewing scheme details."""
    if msg == "1":
        # Go back to results
        await store.update_user_state(phone, ConversationState.SHOW_RESULTS)
        matched_ids = user["matched_schemes"]
        schemes = [get_scheme_by_id(sid) for sid in matched_ids if get_scheme_by_id(sid)]

        if not schemes:
            await store.reset_user(phone)
            return await _welcome_message()

        response = f"📋 Here are your matched schemes again:\n\n"
        for i, scheme in enumerate(schemes[:5], 1):
            response += f"*{i}.* {format_scheme_summary(scheme)}\n\n"
        response += f"_Reply with a number (1–{min(len(schemes), 5)}) for details._"
        return response

    elif msg == "3" or msg in ("restart", "start over", "new"):
        await store.reset_user(phone)
        return await _welcome_message()

    elif msg == "2" or len(msg) > 10:
        # User is asking a question — use LLM fallback
        scheme = get_scheme_by_id(user.get("selected_scheme_id", ""))
        if scheme:
            answer = await ask_llm_fallback(
                user_message=msg if msg != "2" else "Tell me more about this scheme",
                scheme_context=scheme,
                user_profile=user["profile"],
                language=user.get("language", "en"),
            )
            return (
                f"{answer}\n\n"
                "────────────────\n"
                "1️⃣ See another scheme\n"
                "2️⃣ Ask another question\n"
                "3️⃣ Start over"
            )

    return (
        "🤔 Please choose:\n\n"
        "1️⃣ See another scheme\n"
        "2️⃣ Ask a question about this scheme\n"
        "3️⃣ Start over with a new search"
    )


async def _handle_ask_another(phone: str, msg: str) -> str:
    """User had no results and is deciding what to do."""
    if msg in ("1", "different", "category"):
        await store.update_user_state(phone, ConversationState.CATEGORY_SELECTION)
        return (
            "Let's try a different category:\n\n"
            "1️⃣ Student\n"
            "2️⃣ Farmer\n"
            "3️⃣ Job Seeker\n"
            "4️⃣ Other"
        )
    elif msg in ("2", "start over", "restart"):
        await store.reset_user(phone)
        return await _welcome_message()
    else:
        return "Please reply with *1* (try another category) or *2* (start over)."
