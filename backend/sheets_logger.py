"""
Google Sheets Logger - Logs Q&A pairs to Google Sheets
"""
import logging
from typing import Dict, Any, Optional
from datetime import datetime

from n8n_bridge import N8NBridge

logger = logging.getLogger(__name__)


class SheetsLogger:
    """Service for logging questions and answers to Google Sheets"""
    
    def __init__(self, n8n_bridge: N8NBridge, spreadsheet_id: Optional[str] = None):
        self.n8n_bridge = n8n_bridge
        self.spreadsheet_id = spreadsheet_id
        self.sheet_name = "location_qAnda"
        logger.info("SheetsLogger initialized")
    
    async def log_qa_pair(
        self,
        question_id: str,
        question_text: str,
        answer_text: str,
        location_id: str,
        location_name: str,
        schedule_id: str,
        delivery_channel: str,
        timestamp: Optional[datetime] = None
    ) -> bool:
        """
        Log a question/answer pair to Google Sheets
        Returns True if successful
        """
        if not self.spreadsheet_id:
            logger.warning("No spreadsheet_id configured, skipping log")
            return False
        
        try:
            timestamp_str = (timestamp or datetime.utcnow()).isoformat()
            
            # Prepare row data
            row_data = [
                timestamp_str,
                location_id,
                location_name,
                schedule_id,
                question_id,
                question_text,
                answer_text,
                delivery_channel
            ]
            
            # Append to sheet
            result = await self.n8n_bridge.update_spreadsheet(
                spreadsheet_id=self.spreadsheet_id,
                sheet_name=self.sheet_name,
                range="A1",  # Will append after headers
                values=[row_data],
                append=True
            )
            
            logger.info(f"Logged Q&A pair to Sheets: question_id={question_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to log Q&A pair to Sheets: {e}")
            return False
    
    async def ensure_sheet_exists(self) -> bool:
        """
        Ensure the location_qAnda sheet exists with proper headers
        Returns True if sheet exists or was created
        """
        if not self.spreadsheet_id:
            return False
        
        try:
            # Check if sheet exists by trying to read first row
            # If it doesn't exist, create it with headers
            headers = [
                "Timestamp",
                "Location ID",
                "Location Name",
                "Schedule ID",
                "Question ID",
                "Question Text",
                "Answer Text",
                "Delivery Channel"
            ]
            
            # Try to append headers (this will fail if sheet doesn't exist)
            # In production, you'd want to check first
            result = await self.n8n_bridge.update_spreadsheet(
                spreadsheet_id=self.spreadsheet_id,
                sheet_name=self.sheet_name,
                range="A1",
                values=[headers],
                append=False  # Overwrite first row
            )
            
            logger.info(f"Ensured sheet {self.sheet_name} exists with headers")
            return True
            
        except Exception as e:
            logger.error(f"Failed to ensure sheet exists: {e}")
            return False

