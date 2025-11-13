import logging
import sqlite3
from pathlib import Path
from typing import Dict

from config import settings
from backend.n8n_bridge import N8NBridge

logger = logging.getLogger(__name__)


async def execute_google_function(
    function_name: str,
    function_args: dict,
    n8n_bridge: N8NBridge
) -> Dict:
    """
    Execute a Google Workspace function via N8N workflows
    """
    logger.info(f"Executing function: {function_name} with args: {function_args}")

    try:
        if function_name == "create_calendar_event":
            result = await n8n_bridge.create_calendar_event(
                title=function_args.get("summary"),
                description=function_args.get("description", ""),
                start_time=function_args.get("start_time"),
                end_time=function_args.get("end_time"),
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
            import httpx
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://n8n.akir1.app/webhook/tasks",
                    json={"body": {"data": {
                        "operation": "create",
                        "title": function_args.get("title"),
                        "notes": function_args.get("notes", ""),
                        "due": function_args.get("due"),
                        "taskListId": function_args.get("taskListId", "@default")
                    }}},
                    headers={"X-N8N-WEBHOOK-SECRET": settings.n8n_webhook_secret},
                    timeout=30.0
                )
                result = response.json()
            return {"status": "success", "result": result}

        elif function_name == "search_drive":
            import httpx
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://n8n.akir1.app/webhook/drive",
                    json={"body": {"data": {
                        "operation": "search",
                        "query": function_args.get("query"),
                        "pageSize": function_args.get("pageSize", 10)
                    }}},
                    headers={"X-N8N-WEBHOOK-SECRET": settings.n8n_webhook_secret},
                    timeout=30.0
                )
                result = response.json()
            return {"status": "success", "result": result}

        elif function_name in {
            "gmail_operation",
            "calendar_operation",
            "tasks_operation",
            "drive_operation",
            "sheets_operation"
        }:
            service_map = {
                "gmail_operation": "gmail",
                "calendar_operation": "calendar",
                "tasks_operation": "tasks",
                "drive_operation": "drive",
                "sheets_operation": "sheets"
            }
            operation = function_args.get("operation")
            if not operation:
                raise ValueError(f"operation is required for {function_name}")

            result = await n8n_bridge.execute_service_operation(
                service_map[function_name],
                operation,
                function_args.get("parameters") or {}
            )
            return {"status": "success", "result": result}

        elif function_name == "read_memory":
            workspace_path = function_args.get("workspace_path", "/opt/ai-assistant/crecon")
            explicit_db = function_args.get("database_path")

            candidate_paths = [
                Path(explicit_db) if explicit_db else None,
                Path(workspace_path) / ".memory" / "unified_memory.db",
                Path.home() / ".cursor-memory" / "conversations.db",
            ]
            candidate_paths = [p for p in candidate_paths if p is not None]
            db_path = next((p for p in candidate_paths if p.exists()), None)

            if not db_path:
                checked = ", ".join(str(p) for p in candidate_paths)
                error_msg = (
                    "Unified memory database not found. Checked paths: "
                    f"{checked or 'No candidates provided'}"
                )
                logger.error(error_msg)
                return {"status": "error", "error": error_msg}

            try:
                conn = sqlite3.connect(str(db_path))
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                summary = {
                    "active_feature": None,
                    "knowledge": {},
                    "recent_decisions": [],
                    "recent_file_changes": []
                }

                cursor.execute("""
                    SELECT feature_name, description, approach
                    FROM active_feature
                    WHERE workspace_path = ?
                    ORDER BY started_at DESC LIMIT 1
                """, (workspace_path,))
                active = cursor.fetchone()
                if active:
                    summary["active_feature"] = {
                        "name": active["feature_name"],
                        "description": active["description"],
                        "approach": active["approach"]
                    }

                cursor.execute("""
                    SELECT category, key, value
                    FROM knowledge
                    WHERE workspace_path = ?
                """, (workspace_path,))
                for row in cursor.fetchall():
                    if row["category"] not in summary["knowledge"]:
                        summary["knowledge"][row["category"]] = {}
                    summary["knowledge"][row["category"]][row["key"]] = row["value"]

                cursor.execute("""
                    SELECT decision, rationale, category, created_at
                    FROM code_decisions
                    WHERE workspace_path = ?
                    ORDER BY created_at DESC LIMIT 5
                """, (workspace_path,))
                for row in cursor.fetchall():
                    summary["recent_decisions"].append({
                        "decision": row["decision"],
                        "rationale": row["rationale"],
                        "category": row["category"]
                    })

                cursor.execute("""
                    SELECT file_path, change_type, description, success, created_at
                    FROM file_changes
                    WHERE workspace_path = ?
                    ORDER BY created_at DESC LIMIT 10
                """, (workspace_path,))
                for row in cursor.fetchall():
                    summary["recent_file_changes"].append({
                        "file": row["file_path"],
                        "change": row["change_type"],
                        "description": row["description"],
                        "success": bool(row["success"])
                    })

                conn.close()

                return {"status": "success", "memory": summary}

            except Exception as e:
                logger.error(f"Failed to read memory: {e}")
                return {"status": "error", "error": f"Failed to read memory: {str(e)}"}

        elif function_name == "search_contacts":
            import httpx
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://n8n.akir1.app/webhook/contacts",
                    json={"body": {"data": {
                        "operation": "getAll"
                    }}},
                    headers={"X-N8N-WEBHOOK-SECRET": settings.n8n_webhook_secret},
                    timeout=30.0
                )
                contacts_result = response.json()

                query = function_args.get("query", "").lower()
                max_results = function_args.get("max_results", 5)

                if contacts_result.get("success") and contacts_result.get("data"):
                    connections = contacts_result["data"].get("connections", [])
                    matched_contacts = []

                    for contact in connections:
                        names = contact.get("names", [])
                        emails = contact.get("emailAddresses", [])

                        name_match = any(query in (n.get("displayName", "").lower()) for n in names)
                        email_match = any(query in (e.get("value", "").lower()) for e in emails)

                        if name_match or email_match:
                            primary_name = names[0].get("displayName", "") if names else ""
                            primary_email = emails[0].get("value", "") if emails else ""

                            if primary_email:
                                matched_contacts.append({
                                    "name": primary_name,
                                    "email": primary_email
                                })

                                if len(matched_contacts) >= max_results:
                                    break

                    return {"status": "success", "contacts": matched_contacts}
                else:
                    return {"status": "error", "error": "Failed to retrieve contacts"}

        elif function_name == "contacts_operation":
            operation = function_args.get("operation")
            if not operation:
                raise ValueError("operation is required for contacts_operation")
            result = await n8n_bridge.execute_service_operation(
                "contacts",
                operation,
                function_args.get("parameters") or {}
            )
            return {"status": "success", "result": result}

        elif function_name == "workspace_router_action":
            action = function_args.get("action")
            if not action:
                raise ValueError("action is required for workspace_router_action")
            result = await n8n_bridge.execute_router_action(
                action=action,
                data=function_args.get("data") or {},
                async_execution=function_args.get("async", False)
            )
            return {"status": "success", "result": result}

        else:
            return {"status": "error", "error": f"Unknown function: {function_name}"}

    except Exception as e:
        logger.error(f"Error executing {function_name}: {str(e)}")
        return {"status": "error", "error": str(e)}
