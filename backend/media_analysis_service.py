"""
Media Analysis Service
Provides multimodal inspection of images and documents with Gemini + Ollama.
"""
from __future__ import annotations

import base64
import io
import logging
import textwrap
from typing import Optional, Dict

import httpx
from pypdf import PdfReader
from docx import Document

from config import Settings, settings
from models import MediaAnalysisRequest, MediaAnalysisResponse

logger = logging.getLogger(__name__)


class MediaAnalysisService:
    """Utility service that orchestrates cross-provider media analysis."""

    def __init__(self, settings: Settings):
        self.settings = settings

    async def analyze(
        self,
        request: MediaAnalysisRequest,
        gemini_client
    ) -> MediaAnalysisResponse:
        """Run requested engines and aggregate their responses."""
        binary_data = self._decode_base64(request.base64_content)
        extracted_text = None
        if request.include_text_extraction and self._supports_text_extraction(request.mime_type):
            extracted_text = self._extract_text(request.mime_type, binary_data)

        instructions = self._build_prompt(request, extracted_text)

        gemini_result = None
        if "gemini" in request.engines:
            gemini_result = await self._analyze_with_gemini(
                request,
                instructions,
                binary_data,
                gemini_client,
                extracted_text
            )

        ollama_result = None
        if "ollama" in request.engines:
            ollama_result = await self._analyze_with_ollama(
                request,
                instructions,
                binary_data,
                extracted_text
            )

        metadata = {
            "engines": request.engines,
            "analysis_focus": request.analysis_focus
        }

        return MediaAnalysisResponse(
            filename=request.filename,
            mime_type=request.mime_type,
            extracted_text=extracted_text,
            gemini_analysis=gemini_result,
            ollama_analysis=ollama_result,
            metadata=metadata
        )

    def _decode_base64(self, payload: str) -> bytes:
        """Decode base64 payload handling optional data URLs."""
        if payload.startswith("data:"):
            payload = payload.split(",", 1)[1]
        try:
            return base64.b64decode(payload, validate=True)
        except Exception as exc:
            raise ValueError(f"Unable to decode media payload: {exc}") from exc

    def _supports_text_extraction(self, mime_type: str) -> bool:
        return any(
            mime_type.startswith(prefix)
            for prefix in ("text/", "application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        )

    def _extract_text(self, mime_type: str, binary: bytes) -> Optional[str]:
        """Best-effort extraction for textual formats."""
        try:
            if mime_type.startswith("text/"):
                return binary.decode("utf-8", errors="ignore")
            if mime_type == "application/pdf":
                reader = PdfReader(io.BytesIO(binary))
                return "\n".join(page.extract_text() or "" for page in reader.pages).strip()
            if mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
                doc = Document(io.BytesIO(binary))
                return "\n".join(p.text for p in doc.paragraphs if p.text).strip()
        except Exception as exc:
            logger.warning("Failed to extract text from %s: %s", mime_type, exc)
        return None

    def _build_prompt(
        self,
        request: MediaAnalysisRequest,
        extracted_text: Optional[str]
    ) -> str:
        """Construct base prompt shared between engines."""
        focus_map = {
            "summary": "Provide a concise executive summary.",
            "extraction": "List key data points (names, dates, amounts, decisions).",
            "actions": "Identify action items with owners and due dates.",
            "sentiment": "Describe tone/sentiment and potential risks."
        }
        focus_text = "\n".join(focus_map[f] for f in request.analysis_focus if f in focus_map)
        base_context = f"You are analyzing the file '{request.filename}' ({request.mime_type})."
        if request.mime_type.startswith("image/"):
            base_context += " The visual is attached."
        elif extracted_text:
            base_context += " The textual contents are provided below."

        instructions = request.instructions or "Respond in markdown with clear headings."

        prompt = textwrap.dedent(f"""
        {base_context}

        Required focus:
        {focus_text or 'General analysis'}

        Additional instructions:
        {instructions}
        """)

        if extracted_text:
            prompt += "\n\nDocument contents:\n" + extracted_text[:20000]

        return prompt.strip()

    async def _analyze_with_gemini(
        self,
        request: MediaAnalysisRequest,
        prompt: str,
        binary: bytes,
        gemini_client,
        extracted_text: Optional[str]
    ) -> Optional[str]:
        """Call Gemini with best modality support."""
        if gemini_client is None:
            raise ValueError("Gemini client not configured")
        parts = [{"text": prompt}]
        if request.mime_type.startswith(("image/", "application/pdf")) and not extracted_text:
            parts.append({
                "inline_data": {
                    "mime_type": request.mime_type,
                    "data": base64.b64encode(binary).decode("utf-8")
                }
            })

        try:
            response = gemini_client.models.generate_content(
                model=self.settings.premium_llm_model or "gemini-2.0-flash",
                contents=[{"role": "user", "parts": parts}],
                config={"response_mime_type": "text/markdown", "temperature": 0.4}
            )
            return (response.text or "").strip()
        except Exception as exc:
            logger.error("Gemini media analysis failed: %s", exc)
            return None

    async def _analyze_with_ollama(
        self,
        request: MediaAnalysisRequest,
        prompt: str,
        binary: bytes,
        extracted_text: Optional[str]
    ) -> Optional[str]:
        """Call Ollama generate endpoint (vision-capable if image)."""
        url = f"{self.settings.ollama_host.rstrip('/')}/api/generate"
        model = (
            getattr(self.settings, "ollama_vision_model", None)
            or "llava:13b"
            if request.mime_type.startswith("image/")
            else self.settings.default_llm_model
        )
        payload: Dict[str, object] = {
            "model": model,
            "prompt": prompt,
            "stream": False
        }

        if request.mime_type.startswith("image/") and not extracted_text:
            payload["images"] = [base64.b64encode(binary).decode("utf-8")]
        elif extracted_text:
            payload["prompt"] = f"{prompt}\n\nText extracted:\n{extracted_text[:20000]}"

        try:
            async with httpx.AsyncClient(timeout=120) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()
                return data.get("response") or data.get("text")
        except Exception as exc:
            logger.error("Ollama media analysis failed: %s", exc)
            return None


_media_analysis_service: Optional[MediaAnalysisService] = None


def get_media_analysis_service() -> MediaAnalysisService:
    """Expose singleton for FastAPI routes."""
    global _media_analysis_service
    if _media_analysis_service is None:
        _media_analysis_service = MediaAnalysisService(settings)
    return _media_analysis_service
