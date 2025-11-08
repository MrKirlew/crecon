# N8N Workflow Blueprints for Google Ecosystem Integration

This directory contains documentation and templates for N8N workflows that integrate with Google services.

## Overview

The AI Executive Assistant uses N8N as the automation backbone to execute tasks against the Google ecosystem. The FastAPI AI Agent translates user intent into structured JSON payloads and sends them to N8N webhooks with header-based authentication.

## Architecture

```
User Request → FastAPI Agent → RAG Lookup → Intent Recognition → N8N Webhook → Google API
                                    ↓                                              ↓
                              Token Counter                                   Response
```

## Security Configuration

### Webhook Secret Setup

**CRITICAL**: The webhook secret must be synchronized between N8N and FastAPI.

1. Generate a strong secret:
   ```bash
   openssl rand -hex 32
   ```

2. Configure in N8N Webhook node:
   - Authentication: Header Auth
   - Header Name: `X-N8N-WEBHOOK-SECRET`
   - Header Value: `[your generated secret]`

3. Add to `.env` file:
   ```
   N8N_WEBHOOK_SECRET=[same secret as above]
   ```

### Authentication Failure Troubleshooting

If you receive `401 Unauthorized` errors:
- Verify the webhook secret matches in both N8N and FastAPI `.env`
- Check that the N8N Webhook node has Header Auth enabled
- Ensure the header name is exactly `X-N8N-WEBHOOK-SECRET`

## Workflow Templates

### 1. Google Calendar - Event Management

**Webhook URL**: `/webhook/google-calendar`

**Payload Schema**:
```json
{
  "action": "create_event",
  "title": "Meeting with John Doe",
  "start_time": "2025-01-15T14:00:00Z",
  "end_time": "2025-01-15T15:00:00Z",
  "attendees": ["john@example.com"],
  "description": "Discuss Q1 strategy"
}
```

**N8N Workflow Steps**:
1. **Webhook Trigger** (Header Auth)
2. **Function Node** - Parse and validate payload
3. **Google Calendar Node** - Create Event
   - Calendar: Primary
   - Title: `{{ $json.data.title }}`
   - Start: `{{ $json.data.start_time }}`
   - End: `{{ $json.data.end_time }}`
   - Attendees: `{{ $json.data.attendees }}`
   - Description: `{{ $json.data.description }}`
4. **Respond to Webhook** - Return success

**Supported Actions**:
- `create_event` - Create new calendar event
- `update_event` - Update existing event
- `delete_event` - Delete calendar event
- `find_free_slots` - Find available time slots

---

### 2. Gmail - Email Management

**Webhook URL**: `/webhook/gmail`

**Payload Schema**:
```json
{
  "action": "send_email",
  "to": ["recipient@example.com"],
  "subject": "Project Update",
  "body": "<p>HTML email body</p>",
  "cc": [],
  "bcc": [],
  "attachments": []
}
```

**N8N Workflow Steps**:
1. **Webhook Trigger** (Header Auth)
2. **Function Node** - Validate email addresses and format
3. **Gmail Node** - Send Email
   - To: `{{ $json.data.to.join(',') }}`
   - Subject: `{{ $json.data.subject }}`
   - Email Type: HTML
   - Message: `{{ $json.data.body }}`
   - CC: `{{ $json.data.cc.join(',') }}`
   - BCC: `{{ $json.data.bcc.join(',') }}`
4. **Respond to Webhook** - Return message ID

**Supported Actions**:
- `send_email` - Send new email
- `search_emails` - Search inbox
- `get_email` - Retrieve specific email
- `mark_read` - Mark email as read
- `archive_email` - Archive email

---

### 3. Google Sheets - Data Management

**Webhook URL**: `/webhook/google-sheets`

**Payload Schema**:
```json
{
  "action": "append_sheet",
  "spreadsheet_id": "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms",
  "sheet_name": "CRM Leads",
  "range": "A:D",
  "values": [
    ["John Doe", "john@example.com", "555-1234", "2025-01-15"]
  ]
}
```

**N8N Workflow Steps**:
1. **Webhook Trigger** (Header Auth)
2. **Function Node** - Format data for Sheets API
3. **Google Sheets Node** - Append/Update
   - Document: `{{ $json.data.spreadsheet_id }}`
   - Sheet: `{{ $json.data.sheet_name }}`
   - Range: `{{ $json.data.range }}`
   - Data: `{{ $json.data.values }}`
4. **Respond to Webhook** - Return updated range

**Supported Actions**:
- `append_sheet` - Append rows to sheet
- `update_sheet` - Update specific range
- `read_sheet` - Read data from sheet
- `create_sheet` - Create new spreadsheet
- `delete_rows` - Delete specific rows

---

### 4. Google Contacts - Contact Management

**Webhook URL**: `/webhook/google-contacts`

**Payload Schema**:
```json
{
  "action": "search_contacts",
  "query": "John",
  "max_results": 10
}
```

**N8N Workflow Steps**:
1. **Webhook Trigger** (Header Auth)
2. **Google Contacts Node** - Search
   - Operation: Search
   - Query: `{{ $json.data.query }}`
   - Max Results: `{{ $json.data.max_results }}`
3. **Function Node** - Format results
4. **Respond to Webhook** - Return contacts array

**Supported Actions**:
- `search_contacts` - Search contacts by name/email
- `create_contact` - Create new contact
- `update_contact` - Update existing contact
- `get_contact` - Get contact details

---

### 5. Google Drive - Document Management

**Webhook URL**: `/webhook/google-drive`

**Payload Schema**:
```json
{
  "action": "archive_document",
  "document_id": "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms",
  "destination_folder": "Archives/2025",
  "new_name": "Q1_Report_Archived"
}
```

**N8N Workflow Steps**:
1. **Webhook Trigger** (Header Auth)
2. **Google Drive Node** - Move File
   - File ID: `{{ $json.data.document_id }}`
   - Folder: `{{ $json.data.destination_folder }}`
3. **Google Drive Node** - Rename (if new_name provided)
   - Name: `{{ $json.data.new_name }}`
4. **Respond to Webhook** - Return new file location

**Supported Actions**:
- `archive_document` - Move file to archive folder
- `create_folder` - Create new folder
- `search_files` - Search Drive
- `share_file` - Share file with users
- `delete_file` - Move to trash

---

## Google OAuth Setup

All N8N Google integrations require OAuth 2.0 credentials.

### Steps:

1. **Google Cloud Console**:
   - Go to https://console.cloud.google.com
   - Create new project or select existing
   - Enable required APIs:
     - Google Calendar API
     - Gmail API
     - Google Sheets API
     - Google Contacts API
     - Google Drive API

2. **Create OAuth Credentials**:
   - Navigate to "Credentials" → "Create Credentials" → "OAuth client ID"
   - Application type: Web application
   - Authorized redirect URIs: `https://your-domain.com/rest/oauth2-credential/callback`
   - Copy Client ID and Client Secret

3. **Configure in N8N**:
   - Go to N8N → Credentials → Add Credential
   - Select "Google OAuth2 API"
   - Paste Client ID and Secret
   - Click "Connect my account"
   - Authorize required scopes

4. **Required Scopes**:
   ```
   https://www.googleapis.com/auth/calendar
   https://www.googleapis.com/auth/gmail.send
   https://www.googleapis.com/auth/gmail.modify
   https://www.googleapis.com/auth/spreadsheets
   https://www.googleapis.com/auth/contacts
   https://www.googleapis.com/auth/drive
   ```

## Testing Workflows

### Using cURL

```bash
# Test calendar event creation
curl -X POST https://your-domain.com/webhook/google-calendar \
  -H "Content-Type: application/json" \
  -H "X-N8N-WEBHOOK-SECRET: your-secret-here" \
  -d '{
    "action": "create_event",
    "title": "Test Meeting",
    "start_time": "2025-01-20T10:00:00Z",
    "end_time": "2025-01-20T11:00:00Z"
  }'
```

### From FastAPI

The FastAPI AI Agent automatically includes the webhook secret. Test via the chat interface:

```
User: "Schedule a meeting with John tomorrow at 2pm"
```

The agent will:
1. Parse intent → calendar event
2. Call RAG for John's contact info
3. Construct payload with start/end times
4. Send to N8N webhook
5. Return confirmation

## Async Execution

For long-running workflows (>30 seconds):

1. **N8N Workflow**:
   - Add "Respond to Webhook" node immediately after trigger
   - Response: `{ "status": "accepted", "job_id": "{{$workflow.id}}" }`
   - Continue workflow asynchronously
   - Use HTTP Request node to callback FastAPI when complete

2. **FastAPI Configuration**:
   ```python
   result = await n8n_bridge.execute_workflow(
       workflow_name="google-calendar",
       payload=payload,
       async_execution=True  # Don't wait for completion
   )
   ```

## Error Handling

All workflows should include error handling:

1. **Try/Catch Nodes** - Wrap Google API calls
2. **Error Response** - Return structured error:
   ```json
   {
     "success": false,
     "error": "Failed to create event",
     "detail": "Calendar not found"
   }
   ```
3. **Logging** - Log errors to N8N execution history

## Workflow Monitoring

- **N8N UI**: https://your-domain.com/n8n (if exposed)
- **Execution History**: Check N8N database for past executions
- **Langfuse**: All workflow calls are traced if observability is enabled

## Best Practices

1. **Always use Header Authentication** for webhook security
2. **Validate input** in Function nodes before calling Google APIs
3. **Use PostgreSQL** for production (not SQLite)
4. **Set execution timeout** to prevent hanging workflows
5. **Log all executions** for debugging and audit
6. **Test each workflow independently** before integrating with FastAPI
7. **Monitor quota** - Google APIs have rate limits
8. **Use batching** for bulk operations (e.g., 100+ sheet rows)

## Troubleshooting

### Common Issues

**401 Unauthorized**:
- Check webhook secret synchronization
- Verify Header Auth is enabled in N8N

**403 Forbidden (Google API)**:
- Verify OAuth scopes are authorized
- Check Google Cloud Console for API enablement
- Ensure OAuth consent screen is published

**Timeout Errors**:
- Increase nginx proxy timeout
- Use async execution for long operations
- Check Google API latency

**Invalid Payload**:
- Validate JSON schema in Function node
- Check FastAPI logs for payload structure
- Use N8N "Execute Workflow" to test manually

## Next Steps

1. Import workflow templates from `/n8n/workflows/templates/`
2. Configure Google OAuth credentials
3. Test each workflow via N8N UI
4. Integrate with FastAPI agent
5. Enable observability with Langfuse
