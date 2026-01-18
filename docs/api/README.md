# PTC Agent API Reference

## Overview

Base URL: `http://localhost:8000`
Version: 0.1.0

The PTC Agent API provides endpoints for interacting with the PTC (Plan-Think-Code) AI agent system. The agent executes code in isolated Daytona sandboxes and supports real-time streaming responses via Server-Sent Events (SSE).

## Quick Start: Complete API Flow

This section demonstrates the typical workflow for using the PTC Agent API.

### Step 1: Create a Workspace

Create a workspace with a dedicated Daytona sandbox. This provides an isolated environment for code execution.

```bash
curl -X POST "http://localhost:8000/api/v1/workspaces" \
  -H "Content-Type: application/json" \
  -H "X-User-Id: user-123" \
  -d '{
    "name": "My Project",
    "description": "Development workspace for my project"
  }'
```

**Response:**

```json
{
  "workspace_id": "ws-abc123-def456",
  "user_id": "user-123",
  "name": "My Project",
  "description": "Development workspace for my project",
  "sandbox_id": "sandbox-xyz789",
  "status": "running",
  "created_at": "2025-01-15T10:30:00Z",
  "updated_at": "2025-01-15T10:30:00Z"
}
```

### Step 2: Start a Chat Session

Use the workspace to run agent tasks via the streaming chat endpoint. The agent will execute code in the workspace's sandbox.

```bash
curl -N -X POST "http://localhost:8000/api/v1/chat/stream" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user-123",
    "workspace_id": "ws-abc123-def456",
    "messages": [
      {
        "role": "user",
        "content": "Create a Python script that prints Hello World"
      }
    ]
  }'
```

**SSE Response Stream:**

```
event: message_chunk
data: {"content": "I'll create a simple Python script", "agent": "assistant"}

event: tool_calls
data: {"tool_name": "write_file", "arguments": {"path": "/workspace/hello.py", "content": "print('Hello World')"}, "tool_call_id": "call_001"}

event: artifact
data: {"artifact_type": "file_operation", "artifact_id": "call_001", "agent": "ptc", "status": "completed", "payload": {"operation": "write_file", "file_path": "/workspace/hello.py", "line_count": 1}}

event: tool_call_result
data: {"tool_name": "write_file", "result": "File created successfully", "tool_call_id": "call_001"}

event: done
data: {"status": "completed", "thread_id": "thread-xyz"}
```

**Note:** The response includes a `thread_id` which you'll need to reconnect if disconnected.

### Step 3: Reconnect if Disconnected

If your connection drops, you can reconnect to a running or completed workflow using the thread ID:

```bash
curl -N "http://localhost:8000/api/v1/chat/stream/thread-xyz/reconnect"
```

To avoid duplicate events, pass the last event ID you received:

```bash
curl -N "http://localhost:8000/api/v1/chat/stream/thread-xyz/reconnect?last_event_id=42"
```

The reconnect endpoint will:
1. Replay buffered events you may have missed
2. Continue streaming live events if the workflow is still running

### Step 4: Check Workflow Status (Optional)

Check the status of a workflow at any time:

```bash
curl "http://localhost:8000/api/v1/chat/status/thread-xyz"
```

**Response:**

```json
{
  "thread_id": "thread-xyz",
  "status": "completed",
  "workspace_id": "ws-abc123-def456",
  "sandbox_id": "sandbox-xyz789",
  "started_at": "2025-01-15T10:30:00Z",
  "completed_at": "2025-01-15T10:30:45Z"
}
```

### Step 5: Continue the Conversation

Send follow-up messages using the same `workspace_id`:

```bash
curl -N -X POST "http://localhost:8000/api/v1/chat/stream" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user-123",
    "workspace_id": "ws-abc123-def456",
    "messages": [
      {
        "role": "user",
        "content": "Now run the script and show me the output"
      }
    ]
  }'
```

### Complete Flow Diagram

```
┌─────────────────┐      ┌──────────────────┐     ┌─────────────────┐
│  Create         │      │  Chat Stream     │     │  Reconnect      │
│  Workspace      │────▶ │ (with workspace) │────▶│  (if needed)    │
│ POST /workspaces│      │ POST /chat/stream│     │  GET /reconnect │
└─────────────────┘      └──────────────────┘     └─────────────────┘
                               │
                               ▼
                        ┌──────────────────┐
                        │  Continue Chat   │
                        │  (same workspace)│
                        │ POST /chat/stream│
                        └──────────────────┘
```

---

## Authentication

Currently, user identification is handled via:
- `user_id` field in request bodies (for chat endpoints)
- `X-User-Id` header (for workspace endpoints)

## API Groups

| Group | Description | Prefix |
|-------|-------------|--------|
| [Chat](./chat.md) | Streaming chat with SSE, workflow control | `/api/v1/chat` |
| [Workflow](./workflow.md) | Workflow state, checkpoints, cancellation | `/api/v1/workflow` |
| [Workspaces](./workspaces.md) | Workspace CRUD, thread listing, messages | `/api/v1/workspaces` |
| [Cache](./cache.md) | Cache statistics and management | `/api/v1/cache` |
| [Health](./chat.md#health-check) | Health check | `/health` |

## Common Response Formats

### Success Response

```json
{
  "status": "success",
  "data": { ... }
}
```

### Error Response

```json
{
  "detail": "Error message describing what went wrong"
}
```

### Paginated Response

```json
{
  "items": [...],
  "total": 100,
  "limit": 20,
  "offset": 0
}
```

## SSE Event Types

The streaming endpoints emit Server-Sent Events. See [Chat API - SSE Events](./chat.md#sse-event-types) for the complete list of event types.

## Data Models

See [Models Reference](./models.md) for all request/response schemas including:
- ChatRequest / StatusResponse
- WorkspaceCreate / WorkspaceResponse
- WorkspaceThreadListItem / ThreadMessagesResponse

## Rate Limits

No rate limits are currently enforced. This may change in production deployments.

## Versioning

All API endpoints are versioned with the `/api/v1/` prefix. Breaking changes will be introduced in new versions (e.g., `/api/v2/`).
