"""
Pydantic models for engine state and conversation flow.
"""

from enum import Enum
from typing import Optional
from pydantic import BaseModel


class ConversationState(str, Enum):
    """All possible states in the conversation flow."""
    START = "START"
    CATEGORY_SELECTION = "CATEGORY_SELECTION"
    ASK_INCOME = "ASK_INCOME"
    ASK_STATE = "ASK_STATE"
    ASK_SPECIAL_CATEGORY = "ASK_SPECIAL_CATEGORY"
    PROCESS_ELIGIBILITY = "PROCESS_ELIGIBILITY"
    SHOW_RESULTS = "SHOW_RESULTS"
    DEEP_GUIDE = "DEEP_GUIDE"
    ASK_ANOTHER = "ASK_ANOTHER"


class UserCategory(str, Enum):
    STUDENT = "student"
    FARMER = "farmer"
    JOB_SEEKER = "job_seeker"
    OTHER = "other"


class IncomeRange(str, Enum):
    BELOW_1L = "below_1_lakh"
    L1_TO_3L = "1_to_3_lakh"
    L3_TO_5L = "3_to_5_lakh"
    ABOVE_5L = "above_5_lakh"


# Maps income ranges to numeric upper bounds for eligibility matching
INCOME_RANGE_VALUES = {
    IncomeRange.BELOW_1L: 100000,
    IncomeRange.L1_TO_3L: 300000,
    IncomeRange.L3_TO_5L: 500000,
    IncomeRange.ABOVE_5L: 10000000,
}


class UserProfile(BaseModel):
    """Profile built progressively through the conversation."""
    category: Optional[str] = None
    income_range: Optional[str] = None
    income_value: Optional[int] = None  # Upper bound of selected range
    state_name: Optional[str] = None
    special_category: Optional[str] = None
