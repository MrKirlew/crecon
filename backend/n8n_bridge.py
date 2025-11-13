"""
N8N Webhook Bridge - Secure API Communication Layer
Translates AI intent into structured N8N workflow payloads
Implements header-based authentication
"""
import httpx
from typing import Dict, Optional, Any, List
import logging
from config import settings
from datetime import datetime

logger = logging.getLogger(__name__)


class N8NWorkflowError(Exception):
    """Custom exception for N8N workflow execution errors"""
    pass


class N8NBridge:
    """
    Secure bridge between FastAPI AI Agent and N8N Workflow Engine
    Handles payload construction and webhook authentication
    """

    def __init__(self):
        self.webhook_base_url = settings.n8n_webhook_url
        self.webhook_secret = settings.n8n_webhook_secret
        self.timeout = 30.0  # Default timeout for N8N webhooks

    def _get_auth_headers(self) -> Dict[str, str]:
        """
        Generate authentication headers for N8N webhook requests
        Uses custom header-based authentication

        Returns:
            Dict of HTTP headers including webhook secret
        """
        return {
            "Content-Type": "application/json",
            "X-N8N-WEBHOOK-SECRET": self.webhook_secret,
            "User-Agent": "AI-Executive-Assistant/1.0"
        }

    async def _post_webhook(
        self,
        endpoint: str,
        payload: Dict[str, Any],
        timeout: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Helper to POST JSON payloads directly to an N8N webhook endpoint.
        """
        webhook_url = f"{self.webhook_base_url}/{endpoint}"
        headers = self._get_auth_headers()

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    webhook_url,
                    json=payload,
                    headers=headers,
                    timeout=timeout or self.timeout
                )

            if response.status_code >= 400:
                logger.error(
                    f"N8N webhook {endpoint} failed: {response.status_code} - {response.text}"
                )
                raise N8NWorkflowError(
                    f"Webhook {endpoint} failed with status {response.status_code}"
                )

            result = response.json() if response.text else {}
            return {
                "success": True,
                "result": result,
                "status_code": response.status_code
            }

        except httpx.RequestError as e:
            logger.error(f"N8N request error ({endpoint}): {e}")
            raise N8NWorkflowError(f"Failed to connect to N8N ({endpoint}): {str(e)}")

    async def execute_workflow(
        self,
        workflow_name: str,
        payload: Dict[str, Any],
        async_execution: bool = False,
        timeout: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Execute an N8N workflow via webhook

        Args:
            workflow_name: Name/identifier of the N8N workflow
            payload: JSON payload to send to the workflow
            async_execution: If True, don't wait for workflow completion
            timeout: Request timeout in seconds (default: 30s)

        Returns:
            Dict with workflow execution result

        Raises:
            N8NWorkflowError: If workflow execution fails
        """
        # Construct webhook URL
        webhook_url = f"{self.webhook_base_url}/{workflow_name}"

        # Prepare headers
        headers = self._get_auth_headers()

        # Add execution metadata
        execution_payload = {
            "timestamp": datetime.utcnow().isoformat(),
            "workflow": workflow_name,
            "data": payload,
            "async": async_execution
        }

        try:
            logger.info(f"Executing N8N workflow: {workflow_name}")

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    webhook_url,
                    json=execution_payload,
                    headers=headers,
                    timeout=timeout or self.timeout
                )

                # Check for authentication errors
                if response.status_code == 401:
                    logger.error("N8N webhook authentication failed - invalid secret")
                    raise N8NWorkflowError(
                        "Webhook authentication failed. Check N8N_WEBHOOK_SECRET configuration."
                    )

                # Check for other errors
                if response.status_code >= 400:
                    logger.error(
                        f"N8N workflow failed: {response.status_code} - {response.text}"
                    )
                    raise N8NWorkflowError(
                        f"Workflow execution failed: {response.status_code}"
                    )

                # Parse response
                result = response.json() if response.text else {}

                logger.info(f"N8N workflow completed: {workflow_name}")

                return {
                    "success": True,
                    "workflow": workflow_name,
                    "result": result,
                    "status_code": response.status_code,
                    "execution_time": response.elapsed.total_seconds()
                }

        except httpx.TimeoutException:
            logger.error(f"N8N workflow timeout: {workflow_name}")
            raise N8NWorkflowError(f"Workflow timeout after {timeout or self.timeout}s")

        except httpx.RequestError as e:
            logger.error(f"N8N request error: {e}")
            raise N8NWorkflowError(f"Failed to connect to N8N: {str(e)}")

        except Exception as e:
            logger.error(f"Unexpected error executing N8N workflow: {e}")
            raise N8NWorkflowError(f"Workflow execution error: {str(e)}")

    async def create_calendar_event(
        self,
        title: str,
        start_time: str,
        end_time: str,
        attendees: Optional[List[str]] = None,
        description: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a Google Calendar event via N8N calendar workflow

        Args:
            title: Event title
            start_time: ISO 8601 start time
            end_time: ISO 8601 end time
            attendees: List of attendee email addresses
            description: Event description

        Returns:
            Workflow execution result
        """
        payload = {
            "body": {
                "data": {
                    "operation": "create",
                    "title": title,
                    "start_time": start_time,
                    "end_time": end_time,
                    "description": description or "",
                    "attendees": attendees or []
                }
            }
        }

        return await self._post_webhook("calendar", payload)

    async def send_email(
        self,
        to: List[str],
        subject: str,
        body: str,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
        attachments: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Send email via Gmail through N8N gmail workflow

        Args:
            to: List of recipient email addresses
            subject: Email subject
            body: Email body (HTML supported)
            cc: CC recipients
            bcc: BCC recipients
            attachments: List of attachment file paths/URLs

        Returns:
            Workflow execution result
        """
        payload = {
            "body": {
                "data": {
                    "operation": "send",
                    "to": to,
                    "subject": subject,
                    "body": body,
                    "cc": cc or [],
                    "bcc": bcc or []
                }
            }
        }

        return await self._post_webhook("gmail", payload)

    async def update_spreadsheet(
        self,
        spreadsheet_id: str,
        sheet_name: str,
        range: str,
        values: List[List[Any]],
        append: bool = True
    ) -> Dict[str, Any]:
        """
        Update Google Sheets via N8N unified workflow

        Args:
            spreadsheet_id: Google Sheets document ID
            sheet_name: Name of the sheet/tab
            range: Cell range (e.g., "A1:D10")
            values: 2D array of values to write
            append: If True, append to existing data

        Returns:
            Workflow execution result
        """
        payload = {
            "action": "sheets",
            "data": {
                "spreadsheet_id": spreadsheet_id,
                "sheet_name": sheet_name,
                "range": range,
                "values": values,
                "append": append
            }
        }

        return await self.execute_workflow("google-workspace", payload)

    async def search_contacts(
        self,
        query: str,
        max_results: int = 10
    ) -> Dict[str, Any]:
        """
        Search Google Contacts via N8N workflow

        Args:
            query: Search query
            max_results: Maximum number of results

        Returns:
            Workflow execution result with matching contacts
        """
        payload = {
            "action": "search_contacts",
            "query": query,
            "max_results": max_results
        }

        return await self.execute_workflow("contacts/search", payload)

    async def upsert_contact(
        self,
        email: str,
        given_name: Optional[str] = None,
        family_name: Optional[str] = None,
        phone_numbers: Optional[List[str]] = None,
        organization: Optional[str] = None,
        job_title: Optional[str] = None,
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create or update a Google Contact via N8N unified workflow

        Args:
            email: Primary email address (used for lookup)
            given_name: First name
            family_name: Last name
            phone_numbers: List of phone numbers
            organization: Company/organization name
            job_title: Job title
            notes: Additional notes

        Returns:
            Workflow execution result with contact resource name
        """
        payload = {
            "action": "contacts",
            "data": {
                "email": email,
                "given_name": given_name,
                "family_name": family_name,
                "phone_numbers": phone_numbers or [],
                "organization": organization,
                "job_title": job_title,
                "notes": notes
            }
        }

        return await self.execute_workflow("google-workspace", payload)

    async def archive_document(
        self,
        document_id: str,
        destination_folder: str,
        new_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Archive a Google Drive document via N8N workflow

        Args:
            document_id: Google Drive document ID
            destination_folder: Folder ID or path for archiving
            new_name: Optional new name for the document

        Returns:
            Workflow execution result
        """
        payload = {
            "action": "archive_document",
            "document_id": document_id,
            "destination_folder": destination_folder,
            "new_name": new_name
        }

        return await self.execute_workflow("google-drive", payload)

    async def execute_service_operation(
        self,
        service: str,
        operation: str,
        parameters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Generic helper for invoking any Google Workspace service workflow.

        Args:
            service: Service name (gmail, calendar, drive, sheets, contacts, tasks)
            operation: Operation identifier supported by the workflow
            parameters: Operation-specific parameters
        """
        if not service or not operation:
            raise ValueError("service and operation are required")

        payload = {
            "body": {
                "data": {
                    "operation": operation,
                    **(parameters or {})
                }
            }
        }

        return await self._post_webhook(service, payload)

    async def execute_router_action(
        self,
        action: str,
        data: Optional[Dict[str, Any]] = None,
        async_execution: bool = False
    ) -> Dict[str, Any]:
        """
        Call the unified workspace router (service.resource.operation).
        """
        if not action:
            raise ValueError("action is required for router execution")

        payload = {
            "body": {
                "action": action,
                "data": data or {},
                "async": async_execution
            },
            # Duplicate at root for backwards compatibility with workflows that read from $json
            "action": action,
            "data": data or {},
            "async": async_execution
        }

        return await self._post_webhook("workspace-router", payload)

    async def health_check(self) -> bool:
        """
        Check if N8N service is accessible

        Returns:
            True if N8N is responding
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.webhook_base_url.rsplit('/', 1)[0]}/healthz",
                    timeout=5.0
                )
                return response.status_code == 200
        except Exception as e:
            logger.error(f"N8N health check failed: {e}")
            return False


# Global N8N bridge instance
n8n_bridge = None


def get_n8n_bridge() -> N8NBridge:
    """Dependency injection for FastAPI routes"""
    global n8n_bridge
    if n8n_bridge is None:
        n8n_bridge = N8NBridge()
    return n8n_bridge
