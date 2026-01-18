"""Tool argument parsing middleware.

Converts JSON-encoded string arguments to Python objects before tool execution.
"""
import json
import logging

from langchain.agents.middleware import AgentMiddleware

logger = logging.getLogger(__name__)


class ToolArgumentParsingMiddleware(AgentMiddleware):
    """Middleware that parses JSON string arguments to proper Python types.

    This middleware handles cases where LLM providers return tool arguments as
    JSON-encoded strings instead of properly deserialized Python objects.
    It automatically parses string arguments to their proper types before
    tool execution, preventing Pydantic validation errors.

    Common issue: Some LLMs return `'["item1", "item2"]'` (string) instead of
    `["item1", "item2"]` (list), causing validation errors like:
    "Input should be a valid list [type=list_type, input_value='[...]', input_type=str]"
    """

    def _parse_args(self, args):
        """Parse args dict, converting JSON strings to proper types."""
        if not isinstance(args, dict):
            return args

        parsed_args = {}
        for key, value in args.items():
            if isinstance(value, str):
                # Try to parse as JSON if it looks like a JSON structure
                if (value.startswith('[') and value.endswith(']')) or \
                   (value.startswith('{') and value.endswith('}')):
                    try:
                        parsed_args[key] = json.loads(value)
                        logger.debug(f"Parsed JSON string argument '{key}': {value[:50]}... -> {type(parsed_args[key])}")
                    except json.JSONDecodeError:
                        # Not valid JSON, keep as string
                        parsed_args[key] = value
                else:
                    parsed_args[key] = value
            else:
                parsed_args[key] = value

        return parsed_args

    def wrap_tool_call(self, request, handler):
        """Synchronous tool argument parser."""
        # Parse arguments before passing to handler
        if "args" in request.tool_call:
            request.tool_call["args"] = self._parse_args(request.tool_call["args"])
        return handler(request)

    async def awrap_tool_call(self, request, handler):
        """Asynchronous tool argument parser."""
        # Parse arguments before passing to handler
        if "args" in request.tool_call:
            request.tool_call["args"] = self._parse_args(request.tool_call["args"])
        return await handler(request)
