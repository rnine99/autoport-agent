# Artifact Types in Backend Server

## Overview

The backend server supports artifact events through a generic SSE (Server-Sent Events) mechanism. Artifact events are emitted by middleware components to provide real-time updates about specific operations (like todo list updates or file operations) without polluting the agent's conversation context.

## Artifact Event Structure

All artifact events follow this structure:

```json
{
  "artifact_type": "<type>",
  "artifact_id": "<tool_call_id>",
  "agent": "<agent_name>",
  "timestamp": "<ISO_timestamp>",
  "status": "completed" | "failed",
  "payload": { /* type-specific data */ }
}
```

## Available Artifact Types

### 1. `todo_update`

**Source**: `src/ptc_agent/agent/middleware/todo_operations/sse_middleware.py`

**Purpose**: Emits todo list updates when the `TodoWrite` tool is executed.

**Payload Structure**:
```json
{
  "todos": [
    {
      "activeForm": "<form_name>",
      "content": "<task_description>",
      "status": "pending" | "in_progress" | "completed"
    }
  ],
  "total": <number>,
  "completed": <number>,
  "in_progress": <number>,
  "pending": <number>
}
```

**Example Event**:
```json
{
  "artifact_type": "todo_update",
  "artifact_id": "call_function_0l54an3pxzhr_1",
  "agent": "ptc",
  "timestamp": "2026-02-05T21:42:42.004006+00:00",
  "status": "completed",
  "payload": {
    "todos": [
      {
        "activeForm": "Saving task request",
        "content": "Save task request to file",
        "status": "in_progress"
      },
      {
        "activeForm": "Creating test artifact",
        "content": "Create test artifact",
        "status": "pending"
      }
    ],
    "total": 3,
    "completed": 0,
    "in_progress": 1,
    "pending": 2
  }
}
```

**Triggered By**: `TodoWrite` tool calls

---

### 2. `file_operation`

**Source**: `src/ptc_agent/agent/middleware/file_operations/sse_middleware.py`

**Purpose**: Emits file operation updates when `write_file` or `edit_file` tools are executed.

**Payload Structure** (varies by operation):

**For `write_file`**:
```json
{
  "operation": "write_file",
  "file_path": "<full_path>",
  "line_count": <number>,
  "content": "<file_content>"
}
```

**For `edit_file`**:
```json
{
  "operation": "edit_file",
  "file_path": "<full_path>",
  "line_count": <number>,
  "old_string": "<original_content>",
  "new_string": "<replacement_content>"
}
```

**Example Event** (write_file):
```json
{
  "artifact_type": "file_operation",
  "artifact_id": "call_001",
  "agent": "ptc",
  "timestamp": "2026-02-05T21:42:42.004006+00:00",
  "status": "completed",
  "payload": {
    "operation": "write_file",
    "file_path": "/workspace/hello.py",
    "line_count": 1,
    "content": "print('Hello, World!')"
  }
}
```

**Triggered By**: `write_file` and `edit_file` tool calls

---

## How Artifacts Are Processed

### Backend Processing

The artifact events are processed by the `WorkflowStreamHandler` in `src/server/handlers/streaming_handler.py`:

```python
# Generic handler: any event with artifact_type is emitted as artifact SSE
artifact_type = event_data.get("artifact_type")
if artifact_type:
    # Build artifact event with proper structure
    artifact_event = {
        "artifact_type": artifact_type,
        "artifact_id": event_data.get("artifact_id"),
        "agent": agent_name,
        "timestamp": event_data.get("timestamp"),
        "status": event_data.get("status"),
        "payload": event_data.get("payload", {}),
    }
    yield self._format_sse_event("artifact", artifact_event)
```

### Frontend Processing

Currently, artifact events are filtered out in the frontend (`useChatMessages.js`):

```javascript
// Handle artifact events - filter out
if (eventType === 'artifact') {
  /**
   * Filter out artifact events - we don't process or display them in the UI.
   */
  return;
}
```

## Extensibility

The artifact system is designed to be extensible. To add a new artifact type:

1. **Create a middleware** in `src/ptc_agent/agent/middleware/`
2. **Emit events** with the required structure (including `artifact_type`)
3. **The streaming handler** will automatically recognize and emit them as SSE artifact events

The generic handler accepts any `artifact_type` value, so new types can be added without modifying the streaming handler.

## Summary

**Total Artifact Types: 2**

1. ✅ `todo_update` - Todo list updates
2. ✅ `file_operation` - File write/edit operations

Both types are emitted by middleware components and follow the same event structure, making them easy to extend and process.
