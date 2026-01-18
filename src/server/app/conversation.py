"""
Workspace thread and message management endpoints.

This module handles:
- Listing threads in a workspace
- Retrieving workspace messages
- Getting individual message details
"""

import logging
import time
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from src.server.models.conversation import (
    WorkspaceThreadListItem,
    WorkspaceThreadsListResponse,
    ResponseFullDetail,
    MessageQuery,
    MessageResponse,
    WorkspaceMessage,
    WorkspaceMessagesResponse,
)
from src.server.database.conversation_db import (
    get_response_by_id,
    get_workspace_threads,
    get_workspace_messages,
)
from src.server.utils.message_deduplicator import deduplicate_agent_messages

logger = logging.getLogger(__name__)
INTERNAL_SERVER_ERROR_DETAIL = "Internal Server Error"

# Create separate routers for different prefixes
workspaces_threads_router = APIRouter(prefix="/api/v1/workspaces", tags=["Workspace Threads"])
messages_router = APIRouter(prefix="/api/v1/messages", tags=["Messages"])


# ==================== Workspace Thread Management Endpoints ====================
# - Threads are created automatically when first query is sent
# - Users see continuous chat messages per workspace
# - Cost/token usage hidden from user-facing endpoints

@workspaces_threads_router.get("/{workspace_id}/threads", response_model=WorkspaceThreadsListResponse)
async def list_workspace_threads_endpoint(
    workspace_id: str,
    limit: int = Query(20, ge=1, le=100, description="Max threads per page"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    sort_by: str = Query("updated_at", description="Sort field (created_at, updated_at)"),
    sort_order: str = Query("desc", description="Sort order (asc or desc)")
):
    """
    List threads for a workspace with pagination.

    Args:
        workspace_id: Workspace ID (path parameter)
        limit: Maximum threads to return (1-100)
        offset: Pagination offset
        sort_by: Field to sort by
        sort_order: Sort direction

    Returns:
        WorkspaceThreadsListResponse with threads and pagination info

    Raises:
        500: Database error during retrieval
    """
    try:
        logger.info(f"Listing threads for workspace_id={workspace_id}, limit={limit}, offset={offset}")

        threads, total = await get_workspace_threads(
            workspace_id=workspace_id,
            limit=limit,
            offset=offset,
            sort_by=sort_by,
            sort_order=sort_order
        )

        # Build response
        thread_items = [
            WorkspaceThreadListItem(
                thread_id=str(thread["thread_id"]),
                workspace_id=str(thread["workspace_id"]),
                thread_index=thread["thread_index"],
                current_status=thread["current_status"],
                msg_type=thread.get("msg_type"),
                created_at=thread["created_at"],
                updated_at=thread["updated_at"]
            )
            for thread in threads
        ]

        response = WorkspaceThreadsListResponse(
            threads=thread_items,
            total=total,
            limit=limit,
            offset=offset
        )

        logger.info(f"Found {len(threads)} threads for workspace_id={workspace_id}")
        return response

    except Exception as e:
        logger.exception(f"Error listing threads: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list threads: {str(e)}"
        )


@workspaces_threads_router.get("/{workspace_id}/messages", response_model=WorkspaceMessagesResponse)
async def get_workspace_messages_endpoint(
    workspace_id: str,
    limit: int = Query(50, ge=1, le=200, description="Max messages per page"),
    offset: int = Query(0, ge=0, description="Pagination offset")
):
    """
    Get all messages for a workspace across all threads.

    Returns messages chronologically ordered by thread_index then pair_index.
    Includes agent_messages for activity panel rendering.
    Excludes state_snapshot (too heavy).

    Args:
        workspace_id: Workspace ID
        limit: Maximum messages to return (1-200)
        offset: Pagination offset

    Returns:
        WorkspaceMessagesResponse with all messages

    Raises:
        404: Workspace not found
        500: Database error during retrieval
    """
    try:
        logger.info(f"Getting messages for workspace_id={workspace_id}, limit={limit}, offset={offset}")

        # Get workspace and messages
        workspace, messages, total = await get_workspace_messages(
            workspace_id=workspace_id,
            limit=limit,
            offset=offset
        )

        if not workspace:
            raise HTTPException(
                status_code=404,
                detail=f"Workspace not found: {workspace_id}"
            )

        # Build message objects
        message_objects = []
        for msg in messages:
            # Build query object
            query = MessageQuery(
                query_id=str(msg["query_id"]),
                content=msg["query_content"],
                type=msg["query_type"],
                feedback_action=msg.get("feedback_action"),
                metadata=msg.get("query_metadata", {}),
                timestamp=msg["query_timestamp"]
            )

            # Build response object (may be None if response doesn't exist yet)
            response = None
            if msg.get("response_id"):
                # Get file snapshot and operations for this thread
                from src.server.database.conversation_db import get_file_snapshot_before_thread, get_operations_for_thread
                from src.server.models.conversation import FileSnapshot, FileOperationEvent

                file_snapshot = None
                file_operations = None

                try:
                    # Get file snapshot (state before this thread started)
                    snapshot_dict = await get_file_snapshot_before_thread(workspace_id, msg["thread_index"])
                    if snapshot_dict:
                        file_snapshot = {
                            path: FileSnapshot(
                                file_id=info['file_id'],
                                content=info['content'],
                                line_count=info['line_count'],
                                updated_in_thread_id=info['updated_in_thread_id'],
                                updated_in_pair_index=info['updated_in_pair_index']
                            )
                            for path, info in snapshot_dict.items()
                        }

                    # Get operations for this thread/pair
                    operations_list = await get_operations_for_thread(msg["thread_id"], msg["pair_index"])
                    if operations_list:
                        file_operations = [
                            FileOperationEvent(
                                operation=op['operation'],
                                file_path=op['file_path'],
                                content=op['content'] or '',
                                line_count=op.get('line_count', 0),
                                agent=op.get('agent', 'unknown'),
                                thread_id=op['thread_id'],
                                pair_index=op['pair_index'],
                                timestamp=op['timestamp'],
                                operation_index=op['operation_index'],
                                old_string=op.get('old_string'),
                                new_string=op.get('new_string'),
                                tool_call_id=op.get('tool_call_id'),
                                file_id=op['file_id']
                            )
                            for op in operations_list
                        ]

                except Exception as e:
                    logger.warning(f"Failed to get file data for thread {msg['thread_id']}: {e}")
                    # Continue without file data - not critical for response

                response = MessageResponse(
                    response_id=str(msg["response_id"]),
                    status=msg["status"],
                    interrupt_reason=msg.get("interrupt_reason"),
                    agent_messages=msg.get("agent_messages"),
                    execution_time=msg.get("execution_time", 0.0),
                    warnings=msg.get("warnings", []),
                    errors=msg.get("errors", []),
                    timestamp=msg["response_timestamp"],
                    file_snapshot=file_snapshot,
                    file_operations=file_operations
                )

            # Build message pair
            message_objects.append(WorkspaceMessage(
                pair_index=msg["pair_index"],
                thread_id=str(msg["thread_id"]),
                thread_index=msg["thread_index"],
                query=query,
                response=response
            ))

        # Deduplicate agent messages (AIMessage and ToolMessage only)
        dedup_start = time.time()
        message_objects, duplicates_removed = deduplicate_agent_messages(message_objects)
        dedup_time = (time.time() - dedup_start) * 1000  # Convert to ms

        logger.info(
            f"Deduplication for workspace_id={workspace_id}: "
            f"removed {duplicates_removed} duplicates in {dedup_time:.2f}ms"
        )

        # Build response
        response = WorkspaceMessagesResponse(
            workspace_id=str(workspace["workspace_id"]),
            user_id=workspace["user_id"],
            name=workspace.get("name"),
            messages=message_objects,
            total_messages=total,
            has_more=(offset + len(message_objects)) < total,
            created_at=workspace["created_at"],
            updated_at=workspace["updated_at"]
        )

        logger.info(f"Retrieved {len(message_objects)} messages for workspace_id={workspace_id}")
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error getting workspace messages: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get workspace messages: {str(e)}"
        )


@messages_router.get("/{response_id}", response_model=ResponseFullDetail)
async def get_message_detail_endpoint(response_id: str):
    """
    Get complete message/response details by response_id (admin/debug endpoint).

    Includes all fields: state_snapshot, agent_messages, etc.
    This endpoint is for debugging and admin purposes only.

    Args:
        response_id: Response ID

    Returns:
        ResponseFullDetail with state_snapshot and agent_messages

    Raises:
        404: Response not found
        500: Database error during retrieval
    """
    try:
        logger.info(f"Getting full response detail for response_id={response_id}")

        # Get full response detail by response_id
        response_data = await get_response_by_id(response_id)

        if not response_data:
            raise HTTPException(
                status_code=404,
                detail=f"Response not found: {response_id}"
            )

        # Build response model
        # Convert UUID objects to strings for Pydantic validation
        response = ResponseFullDetail(
            response_id=str(response_data["response_id"]),
            thread_id=str(response_data["thread_id"]),
            pair_index=response_data["pair_index"],
            status=response_data["status"],
            interrupt_reason=response_data.get("interrupt_reason"),
            state_snapshot=response_data.get("state_snapshot"),
            agent_messages=response_data.get("agent_messages"),
            metadata=response_data.get("metadata", {}),
            warnings=response_data.get("warnings", []),
            errors=response_data.get("errors", []),
            execution_time=response_data.get("execution_time", 0.0),
            timestamp=response_data["timestamp"]
        )

        logger.info(f"Retrieved full response detail for response_id={response_id}")
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error getting full response detail: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get full response detail: {str(e)}"
        )