"""
Silent Recording Service
Transforms passive meeting recordings into transcripts, summaries,
and orchestrates distribution channels (email + Google Drive).
"""
from __future__ import annotations

import base64
import logging
import textwrap
from typing import Optional, Dict, Any, List
from uuid import uuid4

from config import Settings, settings
from models import (
    SilentRecordingRequest,
    SilentRecordingResponse,
    SilentRecordingSegment,
)
from n8n_bridge import N8NBridge

logger = logging.getLogger(__name__)


class SilentRecordingService:
    """High-level coordinator for silent meeting recording workflows."""

    def __init__(self, settings: Settings):
        self.settings = settings

    async def process_recording(
        self,
        request: SilentRecordingRequest,
        gemini_client=None,
        n8n_bridge: N8NBridge
    ) -> SilentRecordingResponse:
        """
        Orchestrate full pipeline: transcription (if needed), summary generation,
        and optional delivery to Gmail / Google Drive.
        """
        recording_id = str(uuid4())
        transcript_text = await self._resolve_transcript_text(request, gemini_client)
        should_summarize = bool(
            (request.email_delivery and request.email_delivery.include_summary) or
            request.summary_instructions
        )
        summary = None
        if should_summarize:
            if not gemini_client:
                logger.warning("Skipping summary generation - Gemini client not configured")
            else:
                summary = await self._summarize_transcript(
                    transcript_text,
                    request.summary_instructions,
                    gemini_client
                )

        email_result = None
        if request.email_delivery and request.email_delivery.enabled:
            email_result = await self._deliver_via_email(
                request,
                transcript_text,
                summary,
                recording_id,
                n8n_bridge
            )

        drive_result = None
        if request.drive_delivery and request.drive_delivery.enabled:
            drive_result = await self._deliver_to_drive(
                request,
                transcript_text,
                summary,
                recording_id,
                n8n_bridge
            )

        return SilentRecordingResponse(
            recording_id=recording_id,
            transcript_text=transcript_text,
            summary=summary,
            email_delivery=email_result,
            drive_delivery=drive_result
        )

    async def _resolve_transcript_text(
        self,
        request: SilentRecordingRequest,
        gemini_client=None
    ) -> str:
        """Determine transcript text from provided sources."""
        if request.transcript_text:
            return request.transcript_text.strip()
        if request.transcript_segments:
            return self._render_segments(request.transcript_segments)
        if request.audio_base64:
            if not gemini_client:
                raise ValueError("Gemini client required to transcribe audio payloads")
            return await self._transcribe_audio(
                request.audio_base64,
                request.audio_mime_type or "audio/webm",
                gemini_client
            )
        raise ValueError("No transcript data found in silent recording request")

    def _render_segments(self, segments: List[SilentRecordingSegment]) -> str:
        """Format structured segments into plain text transcript."""
        lines = []
        for segment in segments:
            timestamp = f"[{segment.timestamp}] " if segment.timestamp else ""
            speaker = f"{segment.speaker}: " if segment.speaker else ""
            lines.append(f"{timestamp}{speaker}{segment.text}".strip())
        return "\n".join(lines)

    async def _transcribe_audio(
        self,
        audio_base64: str,
        mime_type: str,
        gemini_client
    ) -> str:
        """Use Gemini multimodal abilities to transcribe audio payload."""
        payload = self._normalize_base64(audio_base64)
        try:
            response = gemini_client.models.generate_content(
                model=self.settings.premium_llm_model or "gemini-2.0-flash",
                contents=[{
                    "role": "user",
                    "parts": [
                        {"text": "Transcribe this meeting audio verbatim. Include speaker labels if they can be inferred."},
                        {"inline_data": {"mime_type": mime_type, "data": payload}}
                    ]
                }],
                config={
                    "temperature": 0.1,
                    "response_mime_type": "text/plain"
                }
            )
            transcript = (response.text or "").strip()
            if not transcript:
                raise ValueError("Gemini returned empty transcript")
            return transcript
        except Exception as exc:
            logger.error("Audio transcription failed: %s", exc)
            raise

    async def _summarize_transcript(
        self,
        transcript: str,
        custom_instructions: Optional[str],
        gemini_client
    ) -> Optional[str]:
        """Generate executive summary for transcript using Gemini."""
        if not transcript:
            return None

        instructions = custom_instructions or (
            "Create an executive summary, bullet action items, and next steps."
        )

        prompt = textwrap.dedent(f"""
        Transcript:
        {transcript[:15000]}

        Instructions:
        {instructions}
        """)

        try:
            response = gemini_client.models.generate_content(
                model=self.settings.premium_llm_model or "gemini-2.0-flash",
                contents=[{"role": "user", "parts": [{"text": prompt}]}],
                config={
                    "temperature": 0.35,
                    "response_mime_type": "text/markdown"
                }
            )
            return (response.text or "").strip()
        except Exception as exc:
            logger.warning("Summary generation failed: %s", exc)
            return None

    async def _deliver_via_email(
        self,
        request: SilentRecordingRequest,
        transcript_text: str,
        summary: Optional[str],
        recording_id: str,
        n8n_bridge: N8NBridge
    ) -> Dict[str, Any]:
        """Send transcript via Gmail through N8N workflow."""
        delivery = request.email_delivery
        assert delivery and delivery.enabled

        subject = delivery.subject or f"{request.meeting_title} – Meeting Transcript"
        html_body = self._build_email_body(request, transcript_text, summary, recording_id, delivery.include_summary)

        payload = {
            "to": delivery.to,
            "subject": subject,
            "body": html_body
        }
        if delivery.cc:
            payload["cc"] = delivery.cc
        if delivery.bcc:
            payload["bcc"] = delivery.bcc

        logger.info("Sending silent recording transcript via Gmail to %s", ", ".join(delivery.to))
        return await n8n_bridge.execute_service_operation(
            "gmail",
            "send",
            payload
        )

    async def _deliver_to_drive(
        self,
        request: SilentRecordingRequest,
        transcript_text: str,
        summary: Optional[str],
        recording_id: str,
        n8n_bridge: N8NBridge
    ) -> Dict[str, Any]:
        """Persist transcript to Google Drive."""
        delivery = request.drive_delivery
        assert delivery and delivery.enabled

        file_basename = delivery.file_name or f"{request.meeting_title} – Transcript"
        if delivery.file_format == "text":
            operation = "file.createFromText"
            name = f"{file_basename}.txt"
            payload = {
                "name": name,
                "mimeType": "text/plain",
                "parents": [delivery.parent_folder_id] if delivery.parent_folder_id else [],
                "content": transcript_text
            }
        else:
            operation = "file.createDocFromText"
            name = file_basename
            payload = {
                "name": name,
                "documentContent": transcript_text,
                "summary": summary,
                "folderId": delivery.parent_folder_id
            }

        logger.info("Saving silent recording transcript to Drive as %s (%s)", file_basename, operation)
        drive_result = await n8n_bridge.execute_service_operation(
            "drive",
            operation,
            payload
        )

        if delivery.share_with:
            result_payload = drive_result.get("result", {})
            data_section = result_payload.get("data", {})
            file_id = data_section.get("id") or result_payload.get("id")
            if not file_id:
                logger.warning("Drive response missing file id; skipping share step")
                return drive_result

            for email in delivery.share_with:
                try:
                    await n8n_bridge.execute_service_operation(
                        "drive",
                        "file.share",
                        {
                            "fileId": file_id,
                            "emailAddress": email,
                            "role": "reader"
                        }
                    )
                except Exception as exc:
                    logger.warning("Failed to grant Drive access to %s: %s", email, exc)

        return drive_result

    def _build_email_body(
        self,
        request: SilentRecordingRequest,
        transcript_text: str,
        summary: Optional[str],
        recording_id: str,
        include_summary: bool
    ) -> str:
        """Render HTML payload for email delivery."""
        meta_rows = []
        if request.started_at:
            meta_rows.append(f"<tr><td><strong>Started:</strong></td><td>{request.started_at}</td></tr>")
        if request.ended_at:
            meta_rows.append(f"<tr><td><strong>Ended:</strong></td><td>{request.ended_at}</td></tr>")
        if request.location:
            meta_rows.append(f"<tr><td><strong>Location:</strong></td><td>{request.location}</td></tr>")
        if request.participants:
            meta_rows.append(f"<tr><td><strong>Participants:</strong></td><td>{', '.join(request.participants)}</td></tr>")

        meta_html = "".join(meta_rows)
        summary_html = f"<h3>Summary</h3><div>{summary}</div>" if include_summary and summary else ""
        transcript_html = "<pre style='white-space: pre-wrap; font-family: monospace;'>" \
                          f"{transcript_text}</pre>"

        return textwrap.dedent(f"""
        <div>
            <h2>{request.meeting_title}</h2>
            <table>{meta_html}</table>
            {summary_html}
            <h3>Transcript</h3>
            {transcript_html}
            <p style="color:#999;font-size:12px;">Recording ID: {recording_id}</p>
        </div>
        """)

    def _normalize_base64(self, payload: str) -> str:
        """Strip data URL prefixes and ensure padding."""
        if "," in payload and payload.strip().startswith("data:"):
            payload = payload.split(",", 1)[1]
        payload = payload.strip()
        missing_padding = len(payload) % 4
        if missing_padding:
            payload += "=" * (4 - missing_padding)
        # Validate base64
        try:
            base64.b64decode(payload, validate=True)
        except Exception as exc:
            raise ValueError(f"Invalid audio payload: {exc}") from exc
        return payload


_recording_service: Optional[SilentRecordingService] = None


def get_silent_recording_service() -> SilentRecordingService:
    """Provide singleton instance for FastAPI dependency injection."""
    global _recording_service
    if _recording_service is None:
        _recording_service = SilentRecordingService(settings)
    return _recording_service
