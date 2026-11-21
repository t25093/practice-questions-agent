"""ייצוא השאלות המאושרות לשני קבצי Word: גרסת תלמיד וגרסת מורה."""
from datetime import datetime
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor

FONT = "Arial"
RLM = "\u200f"   # סימן כיוון ימין-לשמאל
FSI, PDI = "\u2068", "\u2069"  # "בידוד": קטע שכיוונו נקבע לפי עצמו (קוד באנגלית לא יתהפך)


def _iso(text: str) -> str:
    return f"{FSI}{text}{PDI}"


def _rtl_paragraph(paragraph):
    """הופך פסקה לימין-לשמאל."""
    p_pr = paragraph._p.get_or_add_pPr()
    bidi = OxmlElement("w:bidi")
    bidi.set(qn("w:val"), "1")
    p_pr.append(bidi)
    paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT


def _add(doc, text, size=12, bold=False, color=None, italic=False, space_after=4, indent=0):
    p = doc.add_paragraph()
    _rtl_paragraph(p)
    p.paragraph_format.space_after = Pt(space_after)
    if indent:
        p.paragraph_format.left_indent = Pt(indent)  # בפסקה מימין-לשמאל, "left" הוא צד ההתחלה (ימין)
    run = p.add_run(text)
    run.font.name = FONT
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.italic = italic
    if color:
        run.font.color.rgb = RGBColor(*color)
    r_pr = run._r.get_or_add_rPr()
    rtl = OxmlElement("w:rtl")
    rtl.set(qn("w:val"), "1")
    r_pr.append(rtl)
    # גופן לעברית (complex script)
    fonts = r_pr.find(qn("w:rFonts"))
    if fonts is None:
        fonts = OxmlElement("w:rFonts")
        r_pr.append(fonts)
    fonts.set(qn("w:cs"), FONT)
    size_cs = OxmlElement("w:szCs")
    size_cs.set(qn("w:val"), str(size * 2))
    r_pr.append(size_cs)
    if bold:
        r_pr.append(OxmlElement("w:bCs"))
    return p


def _build(questions, title, teacher: bool) -> Document:
    doc = Document()
    _add(doc, title, size=20, bold=True, space_after=2)
    if teacher:
        _add(doc, "גרסת מורה – מפתח תשובות", size=13, color=(0xC0, 0x00, 0x00), space_after=14)
    else:
        _add(doc, "שם: ____________________     תאריך: ____________", size=12, space_after=14)

    for n, q in enumerate(questions, start=1):
        _add(doc, f"{RLM}{n}. {_iso(q['question'])}", size=13, bold=True, space_after=4)
        for i, opt in enumerate(q["options"], start=1):
            is_correct = teacher and (i - 1) == q["correct_index"]
            text = f"{RLM}{i}. {_iso(opt)}" + (f"{RLM}   ✓" if is_correct else "")
            _add(doc, text, bold=is_correct, color=(0x00, 0x80, 0x00) if is_correct else None,
                 space_after=2, indent=18)
        if teacher and q.get("source_quote"):
            _add(doc, f"{RLM}מקור בטקסט: \"{_iso(q['source_quote'])}\"", size=10, italic=True,
                 color=(0x60, 0x60, 0x60), space_after=2, indent=18)
        _add(doc, "", space_after=8)
    return doc


def export_to_word(questions, title: str = "שאלות תרגול", out_dir: str = "output") -> dict:
    """יוצר את שני הקבצים ומחזיר את הנתיבים שלהם."""
    folder = Path(out_dir) / datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    folder.mkdir(parents=True, exist_ok=True)
    student = folder / "questions_student.docx"
    teacher = folder / "questions_teacher.docx"
    _build(questions, title, teacher=False).save(student)
    _build(questions, title, teacher=True).save(teacher)
    return {"student": str(student), "teacher": str(teacher)}
