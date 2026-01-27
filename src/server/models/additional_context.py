"""
Additional context models for workflow execution.

Supports flexible context types that can be passed along with user queries.
Contexts are fetched, formatted, and appended to user messages before processing.
"""

from typing import Literal, Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field


class AdditionalContextBase(BaseModel):
    """Base model for additional context with type discrimination."""

    type: str = Field(..., description="Type of context (e.g., 'skills')")
    id: Optional[str] = Field(None, description="Resource identifier for fetching context")


class SkillContext(AdditionalContextBase):
    """Context requesting skill instructions to be loaded for the agent."""

    type: Literal["skills"] = "skills"
    name: str = Field(..., description="Skill name (e.g., 'user-profile')")
    instruction: Optional[str] = Field(
        None,
        description="Additional instruction for the skill (e.g., 'Help the user with first time onboarding')"
    )


# Union type for all context types - used for request validation
# Currently only SkillContext, but designed for extensibility
AdditionalContext = SkillContext


def format_additional_contexts(contexts: List[AdditionalContextBase]) -> str:
    """
    Format multiple additional contexts into a single markdown section.

    Args:
        contexts: List of formatted context strings

    Returns:
        Combined markdown section with separator
    """
    if not contexts:
        return ""

    return "\n\n---\n\n" + "\n\n".join(contexts)
