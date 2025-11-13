# Google Services Integration Guide

**Goal**: Enable users at https://akir1.app to interact with Google services (Calendar, Gmail, Tasks, Drive, Sheets, Contacts) through natural language chat.

**Current Status**:
- ✅ N8N workflows are deployed and active (all 7 workflows)
- ✅ N8N workflows use correct `json.body.data` pattern
- ✅ FastAPI has workflow endpoints (`/api/workflows/*`)
- ❌ Chat UI cannot trigger workflows (missing function calling integration)

---

## Architecture Overview

```
User at https://akir1.app
    ↓
Chat UI (frontend/dist/index.html)
    ↓ POST /api/chat
FastAPI Backend (backend/main.py)
    ↓ (needs function calling)
Gemini AI with Tools
    ↓ function_call
N8N Workflows (https://n8n.akir1.app/webhook/*)
    ↓ OAuth2
Google APIs (Calendar, Gmail, Tasks, etc.)
```

---

## What's Missing

The `/api/chat` endpoint currently:
1. Takes user message
2. Sends to Gemini
3. Returns Gemini's text response

It needs to:
1. Take user message
2. Send to Gemini **WITH function/tool definitions**
3. If Gemini calls a function → Execute N8N workflow
4. Return result to Gemini
5. Gemini formulates final response
6. Return to user

---

## Implementation Options

### Option 1: Simple Function Calling (Recommended)

Modify the Gemini section of `/api/chat` to include tools and handle function calls.

**File**: `/opt/ai-assistant/crecon/backend/main.py`

**Location**: Around line 120-150 (the Gemini section)

**Changes needed**:

```python
# 1. Import google_tools at the top
from google_tools import GOOGLE_WORKSPACE_TOOLS

# 2. Modify Gemini call to include tools
# BEFORE (current):
response = client.models.generate_content(
    model=model,
    contents=gemini_messages,
    config={
        "temperature": temperature,
        "max_output_tokens": max_tokens,
    }
)

# AFTER (with tools):
response = client.models.generate_content(
    model=model,
    contents=gemini_messages,
    config={
        "temperature": temperature,
        "max_output_tokens": max_tokens,
        "tools": GOOGLE_WORKSPACE_TOOLS,  # ADD THIS
    }
)

# 3. Handle function calls
# After getting response, check if it's a function call:
if hasattr(response, 'candidates') and response.candidates:
    candidate = response.candidates[0]
    if hasattr(candidate, 'function_calls') and candidate.function_calls:
        # Gemini wants to call a function!
        for function_call in candidate.function_calls:
            function_name = function_call.name
            function_args = function_call.args

            # Execute the function via N8N
            function_result = await execute_google_function(
                function_name,
                function_args,
                n8n_bridge
            )

            # Send result back to Gemini
            # ... (continue conversation with function result)
```

### Option 2: LangChain Integration (More Complex, More Features)

Use LangChain's Gemini integration with tools - provides better conversation management and multi-step function calling.

### Option 3: Custom Routing (Simpler, Less Flexible)

Parse user intent with keywords and directly call N8N workflows without Gemini function calling.

---

## Recommended Implementation Steps

### ✅ Universal Google Workspace Operations (NEW)

The Gemini tool definition now exposes dedicated functions for **every Google Workspace command** in the N8N stack:

| Function | Coverage |
|----------|----------|
| `gmail_operation` | 17 Gmail actions (send, drafts, labels, threads) |
| `calendar_operation` | 6 Calendar event/availability actions |
| `tasks_operation` | 5 Google Tasks actions |
| `sheets_operation` | 10 Sheets operations (spreadsheets, sheets, rows) |
| `drive_operation` | 17 Drive operations (files, folders, shared drives, search) |
| `contacts_operation` | 5 Contacts CRUD actions |
| `workspace_router_action` | Dot-notation router (`service.resource.operation`) for future endpoints |

Each function accepts an `operation` (enum) plus a free-form `parameters`/`data` object that maps directly to the payload documented in `n8n/workflows/ALL_60_OPERATIONS.md`. This keeps the AI assistant in sync with every new N8N command without redeploying the backend—just add the operation + fields to the workflow and call the same tool.

> Example (append + update rows):
> ```json
> {
>   "name": "sheets_operation",
>   "arguments": {
>     "operation": "row.appendOrUpdate",
>     "parameters": {
>       "spreadsheetId": "SHEET_ID",
>       "sheetName": "Pipeline",
>       "matchColumn": "A",
>       "values": ["Opportunity", "Probability", "Owner"]
>     }
>   }
> }
> ```

The legacy helper tools (`create_calendar_event`, `send_email`, `search_drive`, `search_contacts`, etc.) still exist for quick access, but the new operation-based tools ensure **all 60+ commands** remain available to Gemini, Cursor, and Claude Code automatically.

### Step 1: Create Function Executor

Add this function to `backend/main.py`:

```python
async def execute_google_function(
    function_name: str,
    function_args: dict,
    n8n_bridge: N8NBridge
) -> dict:
    """
    Execute a Google Workspace function via N8N workflows
    """
    try:
        if function_name == "create_calendar_event":
            result = await n8n_bridge.create_calendar_event(
                summary=function_args.get("summary"),
                description=function_args.get("description", ""),
                start_time=function_args.get("start_time"),
                end_time=function_args.get("end_time"),
                timezone=function_args.get("timezone", "UTC"),
                attendees=function_args.get("attendees", [])
            )
            return {"status": "success", "result": result}

        elif function_name == "send_email":
            result = await n8n_bridge.send_email(
                to=function_args.get("to"),
                subject=function_args.get("subject"),
                body=function_args.get("body"),
                cc=function_args.get("cc"),
                bcc=function_args.get("bcc")
            )
            return {"status": "success", "result": result}

        elif function_name == "create_task":
            # Note: You'll need to add this method to N8NBridge
            result = await n8n_bridge.create_task(
                title=function_args.get("title"),
                notes=function_args.get("notes", ""),
                due=function_args.get("due"),
                taskListId=function_args.get("taskListId", "@default")
            )
            return {"status": "success", "result": result}

        elif function_name == "search_drive":
            # Note: You'll need to add this method to N8NBridge
            result = await n8n_bridge.search_drive(
                query=function_args.get("query"),
                pageSize=function_args.get("pageSize", 10)
            )
            return {"status": "success", "result": result}

        else:
            return {"status": "error", "error": f"Unknown function: {function_name}"}

    except Exception as e:
        logger.error(f"Error executing {function_name}: {str(e)}")
        return {"status": "error", "error": str(e)}
```

### Step 2: Add Missing N8NBridge Methods

Add to `backend/n8n_bridge.py`:

```python
async def create_task(
    self,
    title: str,
    notes: str = "",
    due: Optional[str] = None,
    taskListId: str = "@default"
) -> Dict[str, Any]:
    """Create a Google Task"""
    payload = {
        "operation": "create",
        "title": title,
        "taskListId": taskListId
    }
    if notes:
        payload["notes"] = notes
    if due:
        payload["due"] = due

    return await self._call_workflow("https://n8n.akir1.app/webhook/tasks", payload)

async def search_drive(
    self,
    query: str,
    pageSize: int = 10
) -> Dict[str, Any]:
    """Search Google Drive"""
    payload = {
        "operation": "search",
        "query": query,
        "pageSize": pageSize
    }

    return await self._call_workflow("https://n8n.akir1.app/webhook/drive", payload)
```

### Step 3: Update Chat Endpoint Logic

The chat endpoint needs a loop to handle multi-turn function calling:

```python
# Pseudocode structure:
messages_for_gemini = convert_to_gemini_format(request.messages)
max_iterations = 5  # Prevent infinite loops

for iteration in range(max_iterations):
    response = client.models.generate_content(
        model=model,
        contents=messages_for_gemini,
        config={"tools": GOOGLE_WORKSPACE_TOOLS, ...}
    )

    # Check if Gemini wants to call a function
    if has_function_call(response):
        # Execute function
        function_result = await execute_google_function(...)

        # Add function result to conversation
        messages_for_gemini.append(function_result)

        # Continue loop to get Gemini's final response
        continue
    else:
        # Gemini has final text response
        return response.text
        break
```

---

## Testing

Once implemented, users can interact naturally:

### Example 1: Calendar Event
```
User: "Schedule a meeting with john@example.com tomorrow at 2pm for 1 hour to discuss Q4 budget"

Gemini (internally):
1. Parses intent
2. Calls create_calendar_event function
3. N8N creates event in Google Calendar
4. Returns confirmation to user
Response: "✅ I've scheduled a meeting with john@example.com for tomorrow at 2:00 PM - 3:00 PM to discuss Q4 budget."
```

### Example 2: Send Email
```
User: "Send an email to team@company.com with subject 'Weekly Update' saying the project is on track"

Response: "✅ Email sent to team@company.com with subject 'Weekly Update'"
```

### Example 3: Create Task
```
User: "Remind me to review the budget report by Friday"

Response: "✅ Task created: 'Review budget report' due on Friday"
```

### Example 4: Search Drive
```
User: "Find all spreadsheets in my Drive with 'revenue' in the name"

Response: "I found 3 spreadsheets:
1. Q3 Revenue Report.xlsx
2. 2025 Revenue Forecast.xlsx
3. Revenue Analysis Template.xlsx"
```

---

## Current Workflow Endpoints (Already Working)

These are already deployed on your server:

| Workflow | Endpoint | Operations |
|----------|----------|------------|
| Gmail | https://n8n.akir1.app/webhook/gmail | 17 ops (send, draft.*, label.*, thread.*) |
| Calendar | https://n8n.akir1.app/webhook/calendar | 6 ops (create, get, update, delete, list, availability) |
| Tasks | https://n8n.akir1.app/webhook/tasks | 5 ops (create, get, update, delete, list) |
| Sheets | https://n8n.akir1.app/webhook/sheets | 10 ops (spreadsheet ops, row ops, sheet ops) |
| Drive | https://n8n.akir1.app/webhook/drive | 17 ops (files, folders, shared drives, search) |
| Contacts | https://n8n.akir1.app/webhook/contacts | 5 ops (create, get, update, delete, getAll) |
| Router | https://n8n.akir1.app/webhook/workspace-router | Unified router |

All workflows:
- ✅ Use correct `json.body.data` pattern
- ✅ Have valid OAuth2 credentials
- ✅ Are active and ready to use
- ✅ Have been tested and verified

---

## Quick Start (Minimal Implementation)

If you want the quickest path to working Google integration:

### 1. Add Tools Import
Edit `/opt/ai-assistant/crecon/backend/main.py`, add near the top:
```python
from google_tools import GOOGLE_WORKSPACE_TOOLS
```

### 2. Enable Function Calling
Find the Gemini section (around line 130) and add `tools` parameter:
```python
response = client.models.generate_content(
    model=model,
    contents=gemini_messages,
    config={
        "temperature": temperature,
        "max_output_tokens": max_tokens,
        "tools": GOOGLE_WORKSPACE_TOOLS,  # <-- ADD THIS LINE
    }
)
```

### 3. Handle Function Calls (Add After Gemini Response)
```python
# Check if Gemini wants to call a function
if hasattr(response, 'candidates') and response.candidates:
    for part in response.candidates[0].content.parts:
        if hasattr(part, 'function_call'):
            fc = part.function_call
            # For now, just log what function would be called
            logger.info(f"Function call requested: {fc.name} with args: {dict(fc.args)}")
            # TODO: Actually execute the function
            response_text = f"I would call {fc.name} with {dict(fc.args)}, but function execution is not yet implemented."
```

### 4. Test
Restart FastAPI and try:
```
User: "Schedule a meeting tomorrow at 2pm"
```

Gemini should recognize this needs the `create_calendar_event` function.

---

## Files Reference

| File | Location | Purpose |
|------|----------|---------|
| `google_tools.py` | `/opt/ai-assistant/crecon/backend/` | Function definitions for Gemini |
| `main.py` | `/opt/ai-assistant/crecon/backend/` | Main FastAPI app with chat endpoint |
| `n8n_bridge.py` | `/opt/ai-assistant/crecon/backend/` | N8N workflow caller |
| `index.html` | `/opt/ai-assistant/crecon/frontend/dist/` | Chat UI |

---

## Next Steps

1. **Review this guide** to understand the architecture
2. **Choose implementation option** (recommend Option 1: Simple Function Calling)
3. **Implement changes** to `main.py` and `n8n_bridge.py`
4. **Test each function** one at a time
5. **Deploy** and enjoy natural language Google Workspace control!

---

## Support

- **N8N Workflows Fixed**: ✅ All 7 workflows corrected to use `json.body.data`
- **N8N Workflows Active**: ✅ All workflows shown as Active in your screenshot
- **OAuth Credentials**: ✅ All 7 Google services authenticated
- **Backend Endpoints**: ✅ All workflow endpoints exist in FastAPI
- **Missing Piece**: Function calling integration in chat endpoint

Once you implement the function calling, users at https://akir1.app will be able to:
- Schedule calendar events
- Send emails
- Create tasks
- Search Drive
- Manage contacts
- Update spreadsheets

All through natural conversation! 🎉

---

**Created**: 2025-11-12
**Status**: Ready for implementation
**Estimated time**: 1-2 hours for basic implementation
