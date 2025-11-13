"""
Google Workspace Tools for Gemini Function Calling
Integrates with N8N workflows
"""

GMAIL_OPERATIONS = [
    "send",
    "draft.create",
    "draft.get",
    "draft.delete",
    "draft.list",
    "label.create",
    "label.delete",
    "label.get",
    "label.list",
    "thread.addLabel",
    "thread.delete",
    "thread.get",
    "thread.list",
    "thread.removeLabel",
    "thread.reply",
    "thread.trash",
    "thread.untrash"
]

CALENDAR_OPERATIONS = [
    "create",
    "get",
    "update",
    "delete",
    "list",
    "availability"
]

TASKS_OPERATIONS = [
    "create",
    "get",
    "update",
    "delete",
    "list"
]

SHEETS_OPERATIONS = [
    "spreadsheet.create",
    "spreadsheet.delete",
    "row.append",
    "row.update",
    "row.appendOrUpdate",
    "rows.get",
    "rows.delete",
    "sheet.create",
    "sheet.delete",
    "sheet.clear"
]

DRIVE_OPERATIONS = [
    "file.upload",
    "file.download",
    "file.copy",
    "file.move",
    "file.delete",
    "file.share",
    "file.update",
    "file.createFromText",
    "folder.create",
    "folder.delete",
    "folder.share",
    "search",
    "sharedDrive.create",
    "sharedDrive.delete",
    "sharedDrive.get",
    "sharedDrive.list",
    "sharedDrive.update"
]

CONTACTS_OPERATIONS = [
    "create",
    "get",
    "update",
    "delete",
    "getAll"
]

# Define tools/functions that Gemini can call
# Format: {"function_declarations": [...]}
GOOGLE_WORKSPACE_TOOLS = {
    "function_declarations": [
        {
            "name": "create_calendar_event",
            "description": "Create a new event in Google Calendar",
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {
                        "type": "string",
                        "description": "Event title/summary"
                    },
                    "description": {
                        "type": "string",
                        "description": "Event description (optional)"
                    },
                    "start_time": {
                        "type": "string",
                        "description": "Start time in ISO 8601 format (e.g., '2025-11-15T10:00:00')"
                    },
                    "end_time": {
                        "type": "string",
                        "description": "End time in ISO 8601 format (e.g., '2025-11-15T11:00:00')"
                    },
                    "timezone": {
                        "type": "string",
                        "description": "Timezone (e.g., 'America/New_York'). Default: UTC"
                    },
                    "attendees": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of attendee email addresses (optional)"
                    }
                },
                "required": ["summary", "start_time", "end_time"]
            }
        },
        {
            "name": "send_email",
            "description": "Send an email via Gmail",
            "parameters": {
                "type": "object",
                "properties": {
                    "to": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Recipient email address(es)"
                    },
                    "subject": {
                        "type": "string",
                        "description": "Email subject"
                    },
                    "body": {
                        "type": "string",
                        "description": "Email body (HTML or plain text)"
                    },
                    "cc": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "CC email address(es) (optional)"
                    },
                    "bcc": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "BCC email address(es) (optional)"
                    }
                },
                "required": ["to", "subject", "body"]
            }
        },
        {
            "name": "create_task",
            "description": "Create a new task in Google Tasks",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Task title"
                    },
                    "notes": {
                        "type": "string",
                        "description": "Task notes/description (optional)"
                    },
                    "due": {
                        "type": "string",
                        "description": "Due date in ISO 8601 format (optional)"
                    },
                    "taskListId": {
                        "type": "string",
                        "description": "Task list ID (default: '@default')"
                    }
                },
                "required": ["title"]
            }
        },
        {
            "name": "search_drive",
            "description": "Search for files/folders in Google Drive",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query (e.g., 'type:folder', 'name contains \"report\"')"
                    },
                    "pageSize": {
                        "type": "integer",
                        "description": "Number of results to return (default: 10)"
                    }
                },
                "required": ["query"]
            }
        },
        {
            "name": "search_contacts",
            "description": "Search Google Contacts by name or email. Use this to find email addresses for people when only their name is provided.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query - person's name, email, or partial match"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results to return (default: 5)"
                    }
                },
                "required": ["query"]
            }
        },
        {
            "name": "read_memory",
            "description": "Read project memory to get context about the codebase, recent work, technical decisions, and knowledge. Use this when you need information about the project setup, deployment, or past development decisions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "workspace_path": {
                        "type": "string",
                        "description": "Workspace path (default: /opt/ai-assistant/crecon)"
                    },
                    "database_path": {
                        "type": "string",
                        "description": "Optional override for the unified memory SQLite database"
                    }
                },
                "required": []
            }
        },
        {
            "name": "gmail_operation",
            "description": "Access any Gmail command via N8N (send email, manage drafts, labels, or threads). Use this for the 17 Gmail operations documented in ALL_60_OPERATIONS.md.",
            "parameters": {
                "type": "object",
                "properties": {
                    "operation": {
                        "type": "string",
                        "enum": GMAIL_OPERATIONS,
                        "description": "Gmail operation identifier (e.g., 'thread.reply', 'label.list')"
                    },
                    "parameters": {
                        "type": "object",
                        "description": "Operation-specific parameters exactly as expected by the workflow"
                    }
                },
                "required": ["operation"]
            }
        },
        {
            "name": "calendar_operation",
            "description": "Run any Google Calendar workflow: create, update, delete, list, get availability.",
            "parameters": {
                "type": "object",
                "properties": {
                    "operation": {
                        "type": "string",
                        "enum": CALENDAR_OPERATIONS,
                        "description": "Calendar operation identifier"
                    },
                    "parameters": {
                        "type": "object",
                        "description": "Operation-specific fields (eventId, time ranges, etc.)"
                    }
                },
                "required": ["operation"]
            }
        },
        {
            "name": "tasks_operation",
            "description": "Full access to Google Tasks workflows (create, list, update, delete, get).",
            "parameters": {
                "type": "object",
                "properties": {
                    "operation": {
                        "type": "string",
                        "enum": TASKS_OPERATIONS,
                        "description": "Tasks operation identifier"
                    },
                    "parameters": {
                        "type": "object",
                        "description": "Task-specific parameters (taskListId, due, title, etc.)"
                    }
                },
                "required": ["operation"]
            }
        },
        {
            "name": "sheets_operation",
            "description": "Manipulate Google Sheets: spreadsheets, sheets, and rows via the N8N workflow (10 operations).",
            "parameters": {
                "type": "object",
                "properties": {
                    "operation": {
                        "type": "string",
                        "enum": SHEETS_OPERATIONS,
                        "description": "Sheets operation identifier"
                    },
                    "parameters": {
                        "type": "object",
                        "description": "Operation-specific parameters (spreadsheetId, range, values, etc.)"
                    }
                },
                "required": ["operation"]
            }
        },
        {
            "name": "drive_operation",
            "description": "Any Google Drive command: files, folders, shared drives, search (17 operations).",
            "parameters": {
                "type": "object",
                "properties": {
                    "operation": {
                        "type": "string",
                        "enum": DRIVE_OPERATIONS,
                        "description": "Drive operation identifier"
                    },
                    "parameters": {
                        "type": "object",
                        "description": "Operation-specific parameters (fileId, folderId, permissions, etc.)"
                    }
                },
                "required": ["operation"]
            }
        },
        {
            "name": "contacts_operation",
            "description": "Google Contacts CRUD operations (create/get/update/delete/getAll). Use when you already have email/IDs.",
            "parameters": {
                "type": "object",
                "properties": {
                    "operation": {
                        "type": "string",
                        "enum": CONTACTS_OPERATIONS,
                        "description": "Contacts operation identifier"
                    },
                    "parameters": {
                        "type": "object",
                        "description": "Contact fields (given_name, family_name, email, phone numbers, etc.)"
                    }
                },
                "required": ["operation"]
            }
        },
        {
            "name": "workspace_router_action",
            "description": "Call the unified workspace router with dot-notation actions (e.g., 'gmail.email.send', 'calendar.event.list').",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "description": "Service.resource.operation action for the router"
                    },
                    "data": {
                        "type": "object",
                        "description": "Payload forwarded to the workflow"
                    },
                    "async": {
                        "type": "boolean",
                        "description": "Set true to request async execution when supported",
                        "default": False
                    }
                },
                "required": ["action"]
            }
        }
    ]
}
