from __future__ import annotations
import base64
import io
import re
from dataclasses import dataclass, field
from pathlib import Path

from aura.office import read_legacy_bytes, read_legacy_path, read_pptx_bytes, read_xlsx_bytes

_MAX = 24_000

TEXT_EXT = {
    ".py", ".txt", ".md", ".json", ".csv", ".log", ".toml", ".yml", ".yaml",
    ".js", ".ts", ".tsx", ".css", ".html", ".xml", ".ini", ".cfg", ".ps1",
    ".bat", ".rs", ".go", ".java", ".sql", ".c", ".cpp", ".h", ".vbs",
}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".jfif"}
PDF_EXT = {".pdf"}
DOCX_EXT = {".docx"}
DOC_EXT = {".doc"}
XLSX_EXT = {".xlsx"}
XLS_EXT = {".xls"}
PPTX_EXT = {".pptx"}
PPT_EXT = {".ppt"}
BINARY_EXT = PDF_EXT | DOCX_EXT | DOC_EXT | XLSX_EXT | XLS_EXT | PPTX_EXT | PPT_EXT | IMAGE_EXT
OFFICE_EXT = DOCX_EXT | DOC_EXT | XLSX_EXT | XLS_EXT | PPTX_EXT | PPT_EXT
SUPPORTED = TEXT_EXT | IMAGE_EXT | PDF_EXT | OFFICE_EXT


@dataclass
class ReadResult:
    path: Path
    text: str = ""
    image_b64: str = ""
    pages_b64: list[str] = field(default_factory=list)
    kind: str = "text"
    note: str = ""


def _clip(text: str) -> str:
    text = text.strip()
    if len(text) > _MAX:
        return text[:_MAX] + "\n\n[conteúdo truncado]"
    return text


def _pdf_pages_as_b64(data: bytes, max_pages: int = 10) -> list[str]:
    import pymupdf

    doc = pymupdf.open(stream=data, filetype="pdf")
    pages: list[str] = []
    try:
        for i in range(min(len(doc), max_pages)):
            pix = doc.load_page(i).get_pixmap(matrix=pymupdf.Matrix(1.8, 1.8))
            pages.append(base64.b64encode(pix.tobytes("jpeg")).decode("ascii"))
    finally:
        doc.close()
    return pages


def _extract_pdf_text(data: bytes) -> tuple[str, int]:
    text = ""
    page_count = 0
    try:
        import pymupdf

        doc = pymupdf.open(stream=data, filetype="pdf")
        page_count = len(doc)
        parts: list[str] = []
        for i in range(min(page_count, 50)):
            chunk = (doc.load_page(i).get_text() or "").strip()
            if chunk:
                parts.append(chunk)
        doc.close()
        text = "\n\n".join(parts)
    except Exception:
        pass
    if not text.strip():
        try:
            from pypdf import PdfReader

            reader = PdfReader(io.BytesIO(data))
            page_count = len(reader.pages)
            parts = [(p.extract_text() or "").strip() for p in reader.pages[:50]]
            text = "\n\n".join(p for p in parts if p)
        except Exception:
            pass
    return text, page_count or 1


def _read_pdf(data: bytes, path: Path) -> ReadResult:
    if not data.startswith(b"%PDF"):
        return ReadResult(
            path=path,
            note=f"{path.name} chegou corrompido. Feche a AURA, abra de novo e anexe o PDF pelo botão Arquivo.",
        )
    try:
        import pymupdf

        doc = pymupdf.open(stream=data, filetype="pdf")
        page_count = len(doc)
        parts: list[str] = []
        vision_indices: list[int] = []
        try:
            limit = min(page_count, 30)
            for i in range(limit):
                page = doc.load_page(i)
                chunk = (page.get_text() or "").strip()
                has_images = bool(page.get_images())
                if chunk:
                    parts.append(f"--- Página {i + 1} ---\n{chunk}")
                if has_images and not chunk:
                    vision_indices.append(i)
            full_text = "\n\n".join(parts).strip()
            # PDF com texto suficiente: resposta rápida sem moondream
            if len(full_text) >= 120:
                return ReadResult(path=path, text=_clip(full_text), kind="document", note="PDF")
            # Pouco texto: visão só nas páginas vazias com imagem (máx. 3)
            if not vision_indices and not full_text:
                vision_indices = list(range(min(3, limit)))
            elif not vision_indices and full_text:
                vision_indices = [i for i in range(min(2, limit)) if doc.load_page(i).get_images()][:2]
            vision_pages: list[str] = []
            for i in vision_indices[:3]:
                pix = doc.load_page(i).get_pixmap(matrix=pymupdf.Matrix(1.15, 1.15))
                vision_pages.append(base64.b64encode(pix.tobytes("jpeg")).decode("ascii"))
        finally:
            doc.close()
        if vision_pages:
            kind = "pdf_mixed" if full_text else "pdf_scan"
            return ReadResult(
                path=path,
                text=_clip(full_text) if full_text else "",
                kind=kind,
                pages_b64=vision_pages,
                note="PDF com imagens" if kind == "pdf_mixed" else "PDF digitalizado",
            )
        if full_text:
            return ReadResult(path=path, text=_clip(full_text), kind="document", note="PDF")
        return ReadResult(path=path, kind="document", note=f"{path.name} é PDF vazio ou ilegível.")
    except Exception as exc:
        return ReadResult(path=path, note=f"Não consegui abrir {path.name}: {exc}")


def _read_docx(data: bytes, path: Path) -> ReadResult:
    from docx import Document

    doc = Document(io.BytesIO(data))
    lines = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    text = "\n".join(lines)
    if not text:
        return ReadResult(path=path, kind="document", note=f"{path.name} está vazio ou só tem imagens.")
    return ReadResult(path=path, text=_clip(text), kind="document", note="Word")


def read_bytes(name: str, data: bytes) -> ReadResult:
    path = Path(name.replace("\\", "/")).name or "arquivo.bin"
    path = Path(path)
    ext = path.suffix.lower()
    if ext in IMAGE_EXT:
        return ReadResult(
            path=path,
            image_b64=base64.b64encode(data).decode("ascii"),
            kind="image",
            note="imagem",
        )
    if ext in PDF_EXT:
        try:
            return _read_pdf(data, path)
        except Exception as exc:
            return ReadResult(path=path, note=f"Erro ao ler PDF {path.name}: {exc}")
    if ext in DOCX_EXT:
        return _read_docx(data, path)
    if ext in XLSX_EXT:
        text, label = read_xlsx_bytes(data)
        if not text:
            return ReadResult(path=path, kind="document", note=f"{path.name} está vazio.")
        return ReadResult(path=path, text=text, kind="document", note=label)
    if ext in PPTX_EXT:
        text, label = read_pptx_bytes(data)
        if not text:
            return ReadResult(path=path, kind="document", note=f"{path.name} não tem texto nos slides.")
        return ReadResult(path=path, text=text, kind="document", note=label)
    if ext in DOC_EXT | XLS_EXT | PPT_EXT:
        try:
            text, label = read_legacy_bytes(name, data)
        except Exception as exc:
            return ReadResult(path=path, note=str(exc))
        if not text:
            return ReadResult(path=path, kind="document", note=f"{path.name} está vazio.")
        return ReadResult(path=path, text=text, kind="document", note=label)
    if ext in TEXT_EXT or not ext:
        text = data.decode("utf-8", errors="replace").replace("\x00", "")
        if not text.strip():
            return ReadResult(path=path, note=f"{path.name} está vazio.")
        return ReadResult(path=path, text=_clip(text), kind="text")
    return ReadResult(path=path, note=f"Formato {ext} ainda não suportado, senhor.")


def read_path(path: Path) -> ReadResult:
    ext = path.suffix.lower()
    if ext in DOC_EXT | XLS_EXT | PPT_EXT:
        try:
            text, label = read_legacy_path(path)
            if not text:
                return ReadResult(path=path, kind="document", note=f"{path.name} está vazio.")
            return ReadResult(path=path, text=text, kind="document", note=label)
        except Exception as exc:
            return ReadResult(path=path, note=f"Não consegui abrir {path.name}: {exc}")
    try:
        return read_bytes(path.name, path.read_bytes())
    except OSError as exc:
        return ReadResult(path=path, note=f"Não consegui abrir {path.name}: {exc}")


def image_prompt(user_text: str, filename: str) -> str:
    return (
        "Descreva esta imagem em português do Brasil. "
        "Se o senhor pediu algo específico, responda ao pedido com base no que vê.\n"
        f"Arquivo: {filename}\n"
        f"Pedido: {user_text.strip()}"
    )


def pdf_page_prompt(user_text: str, filename: str, page: int, total: int) -> str:
    return (
        f"PDF {filename}, página {page} de {total}. "
        "Leia TODO o texto visível na imagem e descreva tabelas ou figuras importantes. "
        "Responda ao pedido do senhor com base só nesta página.\n"
        f"Pedido: {user_text.strip()}"
    )


def deliver_filename(text: str) -> str:
    if m := re.search(
        r"(?:salv[ae]|grav[ae]|como|nome)\s+[\"']?([\w.\- ]+\.(?:txt|md|json|csv|py|html|docx|pdf|png|xlsx|pptx))",
        text,
        re.I,
    ):
        return m.group(1).strip().replace(" ", "_")
    if m := re.search(r"([\w.\-]+\.(?:txt|md|json|csv|py|html|docx|pdf|png|xlsx|pptx))", text, re.I):
        return m.group(1)
    return "aura_entrega.txt"
