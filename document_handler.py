import os
import shutil
import re
from typing import List, Dict, Any, Tuple
import docx
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
import pypdf
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# Register Unicode fonts for PDF export across Windows and Linux
FONT_CANDIDATES = [
    # Windows
    ("Arial", "C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"),
    ("Times New Roman", "C:/Windows/Fonts/times.ttf", "C:/Windows/Fonts/timesbd.ttf"),
    # Linux / Docker
    ("DejaVuSans", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ("LiberationSans", "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf", "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),
]

ACTIVE_FONT = "Helvetica"
ACTIVE_FONT_BOLD = "Helvetica-Bold"

for name, reg_path, bold_path in FONT_CANDIDATES:
    if os.path.exists(reg_path):
        try:
            pdfmetrics.registerFont(TTFont(name, reg_path))
            ACTIVE_FONT = name
            if os.path.exists(bold_path):
                pdfmetrics.registerFont(TTFont(f"{name}-Bold", bold_path))
                ACTIVE_FONT_BOLD = f"{name}-Bold"
            else:
                ACTIVE_FONT_BOLD = name
            break
        except Exception as e:
            print(f"[Font registration warning] {e}")


def clean_pdf_text_into_paragraphs(raw_text: str) -> List[str]:
    """
    Cleans up extracted PDF text, repairing wrapped lines while preserving paragraphs.
    """
    if not raw_text:
        return []
        
    # Fix hyphenation at line ends (e.g., 'trans-\nlation' -> 'translation')
    text = re.sub(r'(\w+)-\n(\w+)', r'\1\2', raw_text)
    
    # If the text has double newlines, use them as primary paragraph breaks
    if '\n\n' in text or '\n \n' in text:
        raw_blocks = re.split(r'\n\s*\n', text)
        paragraphs = []
        for block in raw_blocks:
            cleaned = re.sub(r'\s*\n\s*', ' ', block.strip())
            cleaned = re.sub(r'[ \t]+', ' ', cleaned).strip()
            if cleaned:
                paragraphs.append(cleaned)
        return paragraphs

    # Otherwise, split by single newline and heuristically assemble paragraphs
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    if not lines:
        return []

    paragraphs = []
    current_para = []

    for i, line in enumerate(lines):
        current_para.append(line)
        is_end = False
        # If line ends with sentence terminator
        if line.endswith(('.', '?', '!', ':', '”', '"')):
            is_end = True
        # If line is short and next line looks like a new heading/sentence
        elif len(line) < 60 and i + 1 < len(lines) and lines[i + 1] and lines[i + 1][0].isupper():
            is_end = True
        elif i + 1 == len(lines):
            is_end = True

        if is_end:
            joined = ' '.join(current_para).strip()
            if joined:
                paragraphs.append(joined)
            current_para = []

    if current_para:
        joined = ' '.join(current_para).strip()
        if joined:
            paragraphs.append(joined)

    return paragraphs


def extract_document(file_path: str) -> Dict[str, Any]:
    """
    Extracts text elements from DOCX, PDF, or TXT file.
    """
    ext = os.path.splitext(file_path)[1].lower()
    elements: List[Dict[str, Any]] = []
    total_words = 0
    estimated_pages = 1

    if ext in ['.docx']:
        doc = docx.Document(file_path)
        elem_id = 0
        
        # 1. Paragraphs
        for p_idx, p in enumerate(doc.paragraphs):
            text = p.text.strip()
            if text:
                words = len(text.split())
                total_words += words
                elements.append({
                    "id": elem_id,
                    "type": "paragraph",
                    "target_index": p_idx,
                    "text": text,
                    "style": p.style.name if p.style else "Normal",
                    "words": words
                })
                elem_id += 1

        # 2. Tables
        for t_idx, table in enumerate(doc.tables):
            for r_idx, row in enumerate(table.rows):
                for c_idx, cell in enumerate(row.cells):
                    cell_text = cell.text.strip()
                    if cell_text:
                        words = len(cell_text.split())
                        total_words += words
                        elements.append({
                            "id": elem_id,
                            "type": "table_cell",
                            "table_idx": t_idx,
                            "row_idx": r_idx,
                            "col_idx": c_idx,
                            "text": cell_text,
                            "words": words
                        })
                        elem_id += 1

        estimated_pages = max(1, total_words // 350)

    elif ext in ['.pdf']:
        elem_id = 0
        try:
            import pymupdf
            doc = pymupdf.open(file_path)
            estimated_pages = len(doc)
            for page_idx, page in enumerate(doc):
                page_text = page.get_text() or ""
                paras = clean_pdf_text_into_paragraphs(page_text)
                for p_text in paras:
                    words = len(p_text.split())
                    total_words += words
                    elements.append({
                        "id": elem_id,
                        "type": "paragraph",
                        "page": page_idx + 1,
                        "text": p_text,
                        "style": "Normal",
                        "words": words
                    })
                    elem_id += 1
        except Exception as e_fitz:
            print(f"[PyMuPDF fallback to pypdf: {e_fitz}]")
            reader = pypdf.PdfReader(file_path)
            estimated_pages = len(reader.pages)
            for page_idx, page in enumerate(reader.pages):
                try:
                    page_text = page.extract_text() or ""
                    paras = clean_pdf_text_into_paragraphs(page_text)
                    for p_text in paras:
                        words = len(p_text.split())
                        total_words += words
                        elements.append({
                            "id": elem_id,
                            "type": "paragraph",
                            "page": page_idx + 1,
                            "text": p_text,
                            "style": "Normal",
                            "words": words
                        })
                        elem_id += 1
                except Exception as e:
                    print(f"[PDF Extraction Error page {page_idx+1}] {e}")

    elif ext in ['.txt', '.md']:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        raw_blocks = re.split(r'\n\s*\n', content)
        elem_id = 0
        for block in raw_blocks:
            t = block.strip()
            if t:
                words = len(t.split())
                total_words += words
                elements.append({
                    "id": elem_id,
                    "type": "paragraph",
                    "text": t,
                    "style": "Normal",
                    "words": words
                })
                elem_id += 1
        estimated_pages = max(1, total_words // 350)

    else:
        raise ValueError(f"Định dạng tệp {ext} không được hỗ trợ. Hãy tải lên tệp .docx, .pdf, hoặc .txt.")

    return {
        "file_type": ext.lstrip('.'),
        "elements": elements,
        "total_paragraphs": len(elements),
        "total_words": total_words,
        "estimated_pages": estimated_pages
    }


def export_docx(
    original_path: str,
    elements: List[Dict[str, Any]],
    translated_map: Dict[int, str],
    output_path: str,
    bilingual: bool = False
) -> str:
    """
    Exports translated content to DOCX.
    If original was DOCX, modifies a copy preserving styles.
    Otherwise, builds a new styled DOCX document.
    """
    ext = os.path.splitext(original_path)[1].lower()

    if ext == '.docx':
        shutil.copyfile(original_path, output_path)
        doc = docx.Document(output_path)

        for elem in elements:
            elem_id = elem["id"]
            trans_text = translated_map.get(elem_id, elem["text"])
            orig_text = elem["text"]

            if elem["type"] == "paragraph":
                p_idx = elem.get("target_index")
                if p_idx is not None and p_idx < len(doc.paragraphs):
                    p = doc.paragraphs[p_idx]
                    if bilingual:
                        p.text = ""
                        r_vi = p.add_run(trans_text + "\n")
                        r_vi.font.size = Pt(11)
                        r_en = p.add_run(orig_text)
                        r_en.font.italic = True
                        r_en.font.size = Pt(9.5)
                        r_en.font.color.rgb = RGBColor(120, 120, 120)
                    else:
                        p.text = trans_text

            elif elem["type"] == "table_cell":
                t_idx = elem.get("table_idx")
                r_idx = elem.get("row_idx")
                c_idx = elem.get("col_idx")
                if t_idx is not None and t_idx < len(doc.tables):
                    table = doc.tables[t_idx]
                    if r_idx < len(table.rows) and c_idx < len(table.rows[r_idx].cells):
                        cell = table.rows[r_idx].cells[c_idx]
                        if bilingual:
                            cell.text = f"{trans_text}\n\n({orig_text})"
                        else:
                            cell.text = trans_text

        doc.save(output_path)
    else:
        # Build fresh DOCX for PDF or TXT input
        doc = docx.Document()
        
        # Set normal font
        style = doc.styles['Normal']
        style.font.name = 'Arial'
        style.font.size = Pt(11)

        for elem in elements:
            elem_id = elem["id"]
            trans_text = translated_map.get(elem_id, elem["text"])
            orig_text = elem["text"]
            
            p = doc.add_paragraph()
            p.paragraph_format.space_after = Pt(6)
            p.paragraph_format.line_spacing = 1.2
            
            if bilingual:
                r_vi = p.add_run(trans_text + "\n")
                r_vi.font.name = 'Arial'
                r_vi.font.size = Pt(11)
                r_en = p.add_run(orig_text)
                r_en.font.name = 'Arial'
                r_en.font.italic = True
                r_en.font.size = Pt(9.5)
                r_en.font.color.rgb = RGBColor(120, 120, 120)
            else:
                r = p.add_run(trans_text)
                r.font.name = 'Arial'
                r.font.size = Pt(11)

        doc.save(output_path)

    return output_path


def export_pdf(
    elements: List[Dict[str, Any]],
    translated_map: Dict[int, str],
    output_path: str,
    title: str = "Bản dịch tài liệu"
) -> str:
    """
    Exports translated content into a clean, readable PDF with Vietnamese font support.
    """
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        rightMargin=45,
        leftMargin=45,
        topMargin=45,
        bottomMargin=45
    )

    styles = getSampleStyleSheet()
    
    font_name = "Arial" if "Arial" in pdfmetrics.getRegisteredFontNames() else "Helvetica"
    font_bold = "Arial-Bold" if "Arial-Bold" in pdfmetrics.getRegisteredFontNames() else font_name

    body_style = ParagraphStyle(
        name="VnBody",
        parent=styles["Normal"],
        fontName=font_name,
        fontSize=10.5,
        leading=16,
        spaceAfter=8
    )

    title_style = ParagraphStyle(
        name="VnTitle",
        parent=styles["Title"],
        fontName=font_bold,
        fontSize=18,
        leading=22,
        alignment=1, # Center
        spaceAfter=18
    )

    story = [
        Paragraph(title, title_style),
        Spacer(1, 12)
    ]

    current_page = None
    for elem in elements:
        elem_id = elem["id"]
        trans_text = translated_map.get(elem_id, elem["text"])
        
        # Check if page changed (for PDF source)
        page_num = elem.get("page")
        if page_num and current_page is not None and page_num != current_page:
            # We can optionally add page indicators or spacers
            story.append(Spacer(1, 6))
        current_page = page_num

        # XML escape for ReportLab
        safe_text = (
            trans_text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace("\n", "<br/>")
        )
        story.append(Paragraph(safe_text, body_style))

    doc.build(story)
    return output_path


def export_txt(
    elements: List[Dict[str, Any]],
    translated_map: Dict[int, str],
    output_path: str,
    bilingual: bool = False
) -> str:
    """
    Exports translated content to plain UTF-8 text.
    """
    with open(output_path, 'w', encoding='utf-8') as f:
        for elem in elements:
            elem_id = elem["id"]
            trans_text = translated_map.get(elem_id, elem["text"])
            orig_text = elem["text"]
            
            if bilingual:
                f.write(f"{trans_text}\n[{orig_text}]\n\n")
            else:
                f.write(f"{trans_text}\n\n")

    return output_path
