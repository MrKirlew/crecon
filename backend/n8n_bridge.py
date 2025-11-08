"""
N8N Webhook Bridge - Secure API Communication Layer
Translates AI intent into structured N8N workflow payloads
Implements header-based authentication
"""
import httpx
from typing import Dict, Optional, Any
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
        Create a Google Calendar event via N8N workflow

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
            "action": "create_event",
            "title": title,
            "start_time": start_time,
            "end_time": end_time,
            "attendees": attendees or [],
            "description": description or ""
        }

        return await self.execute_workflow("google-calendar", payload)

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
        Send email via Gmail through N8N workflow

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
            "action": "send_email",
            "to": to,
            "subject": subject,
            "body": body,
            "cc": cc or [],
            "bcc": bcc or [],
            "attachments": attachments or []
        }

        return await self.execute_workflow("gmail", payload)

    async def update_spreadsheet(
        self,
        spreadsheet_id: str,
        sheet_name: str,
        range: str,
        values: List[List[Any]],
        append: bool = True
    ) -> Dict[str, Any]:
        """
        Update Google Sheets via N8N workflow

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
            "action": "update_sheet" if not append else "append_sheet",
            "spreadsheet_id": spreadsheet_id,
            "sheet_name": sheet_name,
            "range": range,
            "values": values
        }

        return await self.execute_workflow("google-sheets", payload)

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

        return await self.execute_workflow("google-contacts", payload)

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
