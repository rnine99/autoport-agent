"""Deepagent middleware stack factory.

Provides a customizable middleware stack for create_agent() that replaces
the auto-added middlewares from create_deep_agent().
"""

from typing import Any

from deepagents.middleware import FilesystemMiddleware, SubAgentMiddleware
from deepagents.middleware.patch_tool_calls import PatchToolCallsMiddleware
from langchain_anthropic.middleware import AnthropicPromptCachingMiddleware

from ptc_agent.agent.middleware.summarization import SummarizationMiddleware

SUBAGENT_MIDDLEWARE_DESCRIPTION = """Launch a subagent for complex, multi-step tasks.

Args:
    description: Detailed task instructions for the subagent
    subagent_type: Agent type to use

Usage:
- Use for: Complex tasks, isolated research, context-heavy operations
- NOT for: Simple 1-2 tool operations (do directly)
- Parallel: Launch multiple agents in single message for concurrent tasks
- Results: Subagent returns final report only (intermediate steps hidden)

The subagent works autonomously. Provide clear, complete instructions."""


def create_deepagent_middleware(
    model: Any,
    tools: list[Any],
    subagents: list[Any],
    backend: Any,
    skill_sources: list[str] | None = None,
    custom_middleware: list[Any] | None = None,
    llm_map: dict[str, str] | None = None,
) -> list[Any]:
    """Create the deepagent-style middleware stack.

    This factory builds the middleware list that replaces create_deep_agent's
    auto-added middlewares, allowing customization of the task tool description.

    Args:
        model: LLM model instance
        tools: List of tools for the agent
        subagents: List of subagent configurations
        backend: DaytonaBackend instance for FilesystemMiddleware
        skill_sources: List of sandbox paths to skill directories (e.g., ["/home/daytona/skills/user"])
        custom_middleware: Additional middleware to append (e.g., ViewImageMiddleware)
        llm_map: Agent-to-LLM mapping for summarization (uses "summarization" key)

    Returns:
        Complete middleware list for create_agent()
    """
    # Build skills middleware
    skills_middleware: list[Any] = []
    if skill_sources:
        try:
            from deepagents.middleware.skills import SkillsMiddleware as _SkillsMiddleware
        except ImportError as e:
            raise RuntimeError("Skills are enabled but SkillsMiddleware is unavailable") from e

        skills_middleware = [_SkillsMiddleware(backend=backend, sources=skill_sources)]

    # Custom SSE-enabled summarization emits 'summarization_signal' events
    # Returns None if disabled via config
    summarization = SummarizationMiddleware(llm_map=llm_map)

    # Build subagent default middleware (mirrors main middleware structure)
    # Filter None values (summarization may be disabled)
    subagent_default_middleware = [
        m for m in [
            *skills_middleware,
            FilesystemMiddleware(backend=backend),
            summarization,
            AnthropicPromptCachingMiddleware(unsupported_model_behavior="ignore"),
            PatchToolCallsMiddleware(),
        ] if m is not None
    ]

    # Build main middleware stack
    # Filter None values (summarization may be disabled)
    middleware = [
        m for m in [
            *skills_middleware,
            FilesystemMiddleware(backend=backend),
            SubAgentMiddleware(
                default_model=model,
                default_tools=tools,
                subagents=subagents if subagents else [],
                task_description=SUBAGENT_MIDDLEWARE_DESCRIPTION,
                system_prompt=None,  # Disable verbose TASK_SYSTEM_PROMPT injection
                default_middleware=subagent_default_middleware,
                general_purpose_agent=True,
            ),
            summarization,
            AnthropicPromptCachingMiddleware(unsupported_model_behavior="ignore"),
            PatchToolCallsMiddleware(),
        ] if m is not None
    ]

    if custom_middleware:
        middleware.extend(custom_middleware)

    return middleware
