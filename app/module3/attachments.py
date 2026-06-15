"""Client attachment ingestion helpers for chat uploads."""

from __future__ import annotations

import base64
import io
import os
import re
from typing import Any

from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename


def _normalize_text(text: str) -> str:
    compact = re.sub(r"\s+", " ", text or "").strip()
    return compact


def _extract_pdf_text(raw: bytes, *, max_chars: int) -> str:
    try:
        from pypdf import PdfReader  # type: ignore
    except Exception:
        return ""
    try:
        reader = PdfReader(io.BytesIO(raw))
        parts: list[str] = []
        for page in reader.pages[:8]:
            page_text = page.extract_text() or ""
            if page_text.strip():
                parts.append(page_text)
            if sum(len(item) for item in parts) >= max_chars:
                break
        return _normalize_text("\n".join(parts))[:max_chars]
    except Exception:
        return ""


def _extract_docx_text(raw: bytes, *, max_chars: int) -> str:
    try:
        import docx  # type: ignore
    except Exception:
        return ""
    try:
        document = docx.Document(io.BytesIO(raw))
        parts = [paragraph.text.strip() for paragraph in document.paragraphs if paragraph.text and paragraph.text.strip()]
        return _normalize_text("\n".join(parts))[:max_chars]
    except Exception:
        return ""


def _extract_plain_text(raw: bytes, *, max_chars: int) -> str:
    try:
        text = raw.decode("utf-8", errors="ignore")
    except Exception:
        return ""
    return _normalize_text(text)[:max_chars]


def ingest_client_attachments(files: list[FileStorage] | tuple[FileStorage, ...] | None) -> dict[str, Any]:
    max_files = int(os.getenv("CLIENT_MAX_ATTACHMENTS", "6"))
    max_file_bytes = int(os.getenv("CLIENT_MAX_ATTACHMENT_BYTES", str(8 * 1024 * 1024)))
    max_total_bytes = int(os.getenv("CLIENT_MAX_TOTAL_ATTACHMENT_BYTES", str(24 * 1024 * 1024)))
    max_doc_chars = int(os.getenv("CLIENT_ATTACHMENT_TEXT_CHARS", "6000"))
    max_images_to_model = int(os.getenv("CLIENT_MAX_IMAGES_TO_MODEL", "3"))

    uploads = list(files or [])
    if len(uploads) > max_files:
        raise ValueError(f"Too many attachments. Maximum {max_files} files allowed.")

    manifest: list[dict[str, Any]] = []
    extracted_parts: list[str] = []
    image_payloads: list[str] = []
    warnings: list[str] = []
    total_bytes = 0

    for index, upload in enumerate(uploads, start=1):
        raw = upload.read() or b""
        size = len(raw)
        total_bytes += size
        if total_bytes > max_total_bytes:
            raise ValueError("Attachment batch is too large. Please upload smaller files.")
        if size == 0:
            warnings.append(f"Skipped empty file: {upload.filename or f'file-{index}'}")
            continue
        if size > max_file_bytes:
            raise ValueError(f"Attachment exceeds size limit ({max_file_bytes // (1024 * 1024)} MB): {upload.filename}")

        filename = secure_filename(upload.filename or f"attachment-{index}")
        mime = (upload.mimetype or "").lower()
        lower_name = filename.lower()
        item: dict[str, Any] = {"name": filename, "mime": mime or "application/octet-stream", "size_bytes": size}

        if mime.startswith("image/") or lower_name.endswith((".png", ".jpg", ".jpeg", ".webp", ".gif")):
            item["kind"] = "image"
            if len(image_payloads) < max_images_to_model:
                image_payloads.append(base64.b64encode(raw).decode("utf-8"))
            else:
                warnings.append(f"Only the first {max_images_to_model} images are sent to the model.")
            extracted_parts.append(f"[image:{filename}]")
            manifest.append(item)
            continue

        text = ""
        if mime == "application/pdf" or lower_name.endswith(".pdf"):
            item["kind"] = "document"
            text = _extract_pdf_text(raw, max_chars=max_doc_chars)
        elif lower_name.endswith(".docx") or mime in {
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        }:
            item["kind"] = "document"
            text = _extract_docx_text(raw, max_chars=max_doc_chars)
        elif lower_name.endswith((".txt", ".md", ".csv", ".json")) or mime.startswith("text/"):
            item["kind"] = "text"
            text = _extract_plain_text(raw, max_chars=max_doc_chars)
        else:
            item["kind"] = "binary"
            warnings.append(f"Uploaded {filename} but text extraction is not supported for this file type.")

        if text:
            item["extracted_chars"] = len(text)
            extracted_parts.append(f"[file:{filename}] {text}")
        manifest.append(item)

    extracted_text = "\n\n".join(extracted_parts).strip()
    if len(extracted_text) > max_doc_chars:
        extracted_text = extracted_text[:max_doc_chars]

    return {
        "manifest": manifest,
        "image_payloads": image_payloads,
        "extracted_text": extracted_text,
        "warnings": warnings,
    }
