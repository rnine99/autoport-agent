"""File operation utilities for state management and persistence.

This module provides utility functions for file operations that are shared
across the codebase, including:
- FileData type definition
- State reducers for file operations
- Conversion functions between database storage and state formats

These utilities were extracted from the deprecated src/tools/core/filesystem/
module to support active code while that module is being cleaned up.
"""

from datetime import UTC, datetime
from typing import Any, List

from typing_extensions import TypedDict


# Constants
MAX_LINE_LENGTH = 2000


class FileData(TypedDict):
    """Data structure for storing file contents with metadata."""

    content: List[str]
    """Lines of the file."""

    created_at: str
    """ISO 8601 timestamp of file creation."""

    modified_at: str
    """ISO 8601 timestamp of last modification."""


def _file_operations_log_reducer(
    left: list[dict[str, Any]] | None,
    right: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Reducer for file_operations_log: appends new operations with auto-assigned operation_index.

    This reducer:
    1. Accumulates file operations throughout workflow execution
    2. Auto-assigns sequential operation_index per file (0, 1, 2, ...)
    3. Each file_path has its own independent operation sequence

    Args:
        left: Existing operations list (or None if first update)
        right: New operations to append

    Returns:
        Concatenated list of all operations with operation_index assigned

    Example:
        # First update: left=None, right=[{file_path: "/a.py"}, {file_path: "/b.py"}]
        #   → [{file_path: "/a.py", operation_index: 0}, {file_path: "/b.py", operation_index: 0}]
        # Second update: left=[...], right=[{file_path: "/a.py"}]
        #   → [..., {file_path: "/a.py", operation_index: 1}]
    """
    # Track max operation_index per file_path
    file_indices: dict[str, int] = {}

    if left is not None:
        # Scan existing operations to find max index for each file
        for op in left:
            file_path = op.get("file_path")
            if file_path:
                current_max = file_indices.get(file_path, -1)
                op_index = op.get("operation_index", -1)
                file_indices[file_path] = max(current_max, op_index)

    # Assign sequential indices to new operations
    for op in right:
        file_path = op.get("file_path")
        if file_path and "operation_index" not in op:
            # Get next index for this file (start from 0 if file not seen before)
            next_index = file_indices.get(file_path, -1) + 1
            op["operation_index"] = next_index
            file_indices[file_path] = next_index

    if left is None:
        return right
    return left + right  # Append, don't replace


def _create_file_data(
    content: str | list[str],
    *,
    created_at: str | None = None,
) -> FileData:
    r"""Create a FileData object with automatic timestamp generation.

    Args:
        content: File content as string or list of lines
        created_at: Optional creation timestamp (ISO 8601)

    Returns:
        FileData with content split into lines and timestamps set
    """
    lines = content.split("\n") if isinstance(content, str) else content
    lines = [line[i:i+MAX_LINE_LENGTH] for line in lines for i in range(0, len(line) or 1, MAX_LINE_LENGTH)]
    now = datetime.now(UTC).isoformat()

    return {
        "content": lines,
        "created_at": created_at or now,
        "modified_at": now,
    }


def _file_data_to_string(file_data: FileData) -> str:
    r"""Convert FileData to plain string content.

    Args:
        file_data: FileData object with content as list of lines

    Returns:
        String with lines joined by newlines
    """
    return "\n".join(file_data["content"])


def string_to_file_data(
    content: str,
    created_at: str | None = None,
    modified_at: str | None = None
) -> FileData:
    """Convert a string to FileData format (list of lines).

    This is the inverse of _file_data_to_string() and is used for
    loading files from database back into state. Ensures bidirectional
    conversion between database storage (string) and state format (list[str]).

    Args:
        content: String content to convert
        created_at: Optional creation timestamp (ISO 8601)
        modified_at: Optional modification timestamp (ISO 8601)

    Returns:
        FileData with content as list[str]

    Example:
        >>> db_content = "Line 1\\nLine 2\\nLine 3"
        >>> file_data = string_to_file_data(db_content)
        >>> file_data['content']
        ['Line 1', 'Line 2', 'Line 3']
        >>> len(file_data['content'])
        3
    """
    # Use _create_file_data for consistency (handles line chunking)
    file_data = _create_file_data(content, created_at=created_at)

    # Override modified_at if provided (created_at is already set by _create_file_data)
    if modified_at:
        file_data['modified_at'] = modified_at

    return file_data
