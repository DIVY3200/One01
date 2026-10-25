from rag.ingest import chunk_sections, extract_sections, markdown_sections, split_text, strip_quiz_blocks

from helpers import BACKPROP_MD, OPTIMIZERS_PDF


def test_split_respects_size_and_keeps_every_paragraph():
    text = "\n\n".join(f"Paragraph {i}. " + "word " * 60 for i in range(10))
    chunks = split_text(text, 400, 80)
    assert len(chunks) >= 7
    assert all(len(c) <= 400 for c in chunks)
    joined = " ".join(chunks)
    assert all(f"Paragraph {i}." in joined for i in range(10))


def test_consecutive_chunks_overlap():
    text = "\n\n".join(f"Paragraph {i}. " + "word " * 60 for i in range(10))
    chunks = split_text(text, 400, 80)
    assert any(chunks[i][-30:].split()[-1] in chunks[i + 1] for i in range(len(chunks) - 1))


def test_hard_split_when_there_is_no_separator():
    assert split_text("x" * 2500, 1000, 100)[0] == "x" * 1000


def test_markdown_chunks_remember_their_heading():
    sections = markdown_sections(BACKPROP_MD)
    assert [s.heading for s in sections] == ["Backpropagation in Machine Learning", "Vanishing gradients", "Weight update"]
    chunks = chunk_sections(sections, 1000, 150)
    assert any(c.heading == "Vanishing gradients" and "sigmoid" in c.text for c in chunks)


def test_pdf_sections_are_split_by_page():
    sections = extract_sections("optimizers.pdf", OPTIMIZERS_PDF)
    assert [s.page for s in sections] == [1, 2]
    assert "Adam" in sections[1].text


def test_quiz_blocks_are_stripped_from_lessons():
    assert strip_quiz_blocks('Intro\n```quiz\n{"q": 1}\n```\nEnd') == "Intro\n\nEnd"
