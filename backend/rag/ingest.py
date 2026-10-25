"""Document loading and chunking."""
import io
import os
import re
from dataclasses import dataclass
from typing import List, Optional

SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".md", ".markdown"}

_SEPARATORS = ["\n\n", "\n", ". ", " ", ""]
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
_QUIZ_BLOCK_RE = re.compile(r"```quiz[\s\S]*?```")
_MIN_CHUNK_CHARS = 40


@dataclass
class Section:
    text: str
    page: Optional[int] = None
    heading: Optional[str] = None


@dataclass
class Chunk:
    text: str
    page: Optional[int] = None
    heading: Optional[str] = None


class UnsupportedFileError(ValueError):
    pass


# ─── Loading ──────────────────────────────────────────────────────
def extract_sections(filename: str, data: bytes) -> List[Section]:
    """Turn an uploaded file into text sections that remember their page / heading."""
    ext = os.path.splitext(filename)[1].lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise UnsupportedFileError(f"Unsupported file type '{ext}'. Upload PDF, Markdown or text files.")
    if ext == ".pdf":
        return _pdf_sections(data)
    text = data.decode("utf-8-sig", errors="replace")
    return markdown_sections(clean_text(text))


def _pdf_sections(data: bytes) -> List[Section]:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    if reader.is_encrypted:
        reader.decrypt("")
    sections = []
    for page_no, page in enumerate(reader.pages, start=1):
        text = clean_text(page.extract_text() or "")
        if text:
            sections.append(Section(text=text, page=page_no))
    return sections


def markdown_sections(text: str) -> List[Section]:
    """Split on Markdown headings so every chunk knows which section it came from."""
    sections: List[Section] = []
    heading: Optional[str] = None
    buf: List[str] = []

    def flush():
        body = "\n".join(buf).strip()
        if body:
            sections.append(Section(text=body, heading=heading))

    for line in text.splitlines():
        match = _HEADING_RE.match(line)
        if match:
            flush()
            buf = []
            heading = match.group(2).strip()
        buf.append(line)
    flush()
    return sections


def clean_text(text: str) -> str:
    text = text.replace("\x00", "")
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)  # re-join words hyphenated across lines
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def strip_quiz_blocks(markdown: str) -> str:
    """Lesson text without the interactive ```quiz JSON blocks."""
    return _QUIZ_BLOCK_RE.sub("", markdown).strip()


# ─── Chunking ─────────────────────────────────────────────────────
def chunk_sections(sections: List[Section], size: int, overlap: int) -> List[Chunk]:
    chunks = []
    for section in sections:
        for text in split_text(section.text, size, overlap):
            if len(text) >= _MIN_CHUNK_CHARS:
                chunks.append(Chunk(text=text, page=section.page, heading=section.heading))
    return chunks


def split_text(text: str, size: int, overlap: int) -> List[str]:
    """Recursive character splitter.

    Prefers paragraph, then line, then sentence, then word boundaries, and
    carries `overlap` characters of trailing context into the next chunk.
    """
    pieces = _split_recursive(text.strip(), size, _SEPARATORS)
    return _merge(pieces, size, overlap)


def _split_recursive(text: str, size: int, separators: List[str]) -> List[str]:
    if len(text) <= size:
        return [text] if text else []
    sep, rest = separators[0], separators[1:]
    if sep == "":
        return [text[i:i + size] for i in range(0, len(text), size)]
    if sep not in text:
        return _split_recursive(text, size, rest)

    parts = text.split(sep)
    pieces = []
    for i, part in enumerate(parts):
        if i < len(parts) - 1:
            part += sep  # keep the separator so merging is lossless
        if not part:
            continue
        if len(part) > size:
            pieces.extend(_split_recursive(part, size, rest))
        else:
            pieces.append(part)
    return pieces


def _merge(pieces: List[str], size: int, overlap: int) -> List[str]:
    chunks: List[str] = []
    current: List[str] = []
    length = 0
    for piece in pieces:
        if current and length + len(piece) > size:
            chunks.append("".join(current).strip())
            # Drop pieces from the front until only the overlap window remains.
            while current and (length > overlap or length + len(piece) > size):
                length -= len(current[0])
                current.pop(0)
        current.append(piece)
        length += len(piece)
    if current:
        chunks.append("".join(current).strip())
    return [c for c in chunks if c]
