"""
Kautilya AI — Artifact Service
Generates downloadable artifacts (Excel, PDF, DOCX, CSV, Markdown) from
structured content or markdown text. Used by `/api/artifact/*` routes.
"""
import io
import re
import csv
import json
from typing import Optional, Tuple


# ============================================================
# Markdown Table Parser (used by Excel/CSV generators)
# ============================================================

def parse_markdown_tables(md: str) -> list:
    """Extract markdown tables from text. Returns list of {header, rows}."""
    tables = []
    lines = md.split('\n')
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        # Header row must contain pipes
        if '|' in line and i + 1 < len(lines):
            sep = lines[i + 1].strip()
            # Separator line: |---|---|
            if re.match(r'^\|?[\s\-:|]+\|[\s\-:|]+\|?$', sep):
                header = [c.strip() for c in line.strip('|').split('|')]
                rows = []
                j = i + 2
                while j < len(lines) and '|' in lines[j].strip():
                    row = [c.strip() for c in lines[j].strip().strip('|').split('|')]
                    rows.append(row)
                    j += 1
                tables.append({'header': header, 'rows': rows})
                i = j
                continue
        i += 1
    return tables


# ============================================================
# EXCEL Generator
# ============================================================

def generate_excel(content: str, filename: str = "kautilya_artifact.xlsx",
                   title: str = "Kautilya Export") -> Tuple[io.BytesIO, str]:
    """Generate Excel file from structured content.
    
    Content can be:
      - JSON: {"sheets": [{"name": "...", "header": [...], "rows": [[...]]}]}
      - Markdown with tables
      - Plain text (single column)
    """
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment
    except ImportError:
        raise RuntimeError("openpyxl not installed")

    wb = openpyxl.Workbook()
    wb.remove(wb.active)

    header_font = Font(bold=True, color="FFFFFF", size=11)
    header_fill = PatternFill(start_color="4F46E5", end_color="4F46E5", fill_type="solid")
    header_align = Alignment(horizontal="center", vertical="center")

    # Try JSON structured input first
    try:
        data = json.loads(content) if isinstance(content, str) else content
        if isinstance(data, dict) and 'sheets' in data:
            for sheet in data['sheets']:
                ws = wb.create_sheet(title=sheet.get('name', 'Sheet')[:31])
                header = sheet.get('header', [])
                rows = sheet.get('rows', [])
                if header:
                    ws.append(header)
                    for col_idx in range(1, len(header) + 1):
                        cell = ws.cell(row=1, column=col_idx)
                        cell.font = header_font
                        cell.fill = header_fill
                        cell.alignment = header_align
                for r in rows:
                    ws.append(r)
                # Auto-width
                for col in ws.columns:
                    max_len = max((len(str(c.value or '')) for c in col), default=10)
                    ws.column_dimensions[col[0].column_letter].width = min(max_len + 2, 50)
            buf = io.BytesIO()
            wb.save(buf)
            buf.seek(0)
            return buf, filename
    except (json.JSONDecodeError, TypeError, KeyError):
        pass

    # Try markdown tables
    tables = parse_markdown_tables(content)
    if tables:
        for idx, tbl in enumerate(tables):
            ws = wb.create_sheet(title=f"Table{idx + 1}")
            ws.append(tbl['header'])
            for col_idx in range(1, len(tbl['header']) + 1):
                cell = ws.cell(row=1, column=col_idx)
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = header_align
            for r in tbl['rows']:
                ws.append(r)
            for col in ws.columns:
                max_len = max((len(str(c.value or '')) for c in col), default=10)
                ws.column_dimensions[col[0].column_letter].width = min(max_len + 2, 50)
    else:
        # Plain text fallback
        ws = wb.create_sheet(title=title[:31])
        ws.append([title])
        ws['A1'].font = Font(bold=True, size=14)
        for line in content.split('\n'):
            ws.append([line])

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf, filename


# ============================================================
# PDF Generator (with markdown support)
# ============================================================

def generate_pdf(content: str, filename: str = "kautilya_artifact.pdf",
                 title: str = "Kautilya Export") -> Tuple[io.BytesIO, str]:
    """Generate PDF from markdown content with basic formatting."""
    try:
        from fpdf import FPDF
    except ImportError:
        raise RuntimeError("fpdf2 not installed")

    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    # Title
    pdf.set_font("Helvetica", 'B', 16)
    safe_title = title.encode('latin-1', 'replace').decode('latin-1')
    pdf.cell(0, 10, safe_title, ln=True)
    pdf.ln(2)

    # Body — parse simple markdown
    pdf.set_font("Helvetica", size=11)
    lines = content.split('\n')
    in_code = False
    
    for line in lines:
        safe_line = line.encode('latin-1', 'replace').decode('latin-1')
        
        # Code fence
        if line.strip().startswith('```'):
            in_code = not in_code
            pdf.set_font("Courier", size=9) if in_code else pdf.set_font("Helvetica", size=11)
            continue
        
        if in_code:
            pdf.set_fill_color(245, 245, 250)
            pdf.multi_cell(0, 5, safe_line, fill=True)
            continue

        # Headings
        if line.startswith('# '):
            pdf.set_font("Helvetica", 'B', 14)
            pdf.cell(0, 8, safe_line[2:], ln=True)
            pdf.set_font("Helvetica", size=11)
            pdf.ln(1)
        elif line.startswith('## '):
            pdf.set_font("Helvetica", 'B', 12)
            pdf.cell(0, 7, safe_line[3:], ln=True)
            pdf.set_font("Helvetica", size=11)
        elif line.startswith('### '):
            pdf.set_font("Helvetica", 'B', 11)
            pdf.cell(0, 6, safe_line[4:], ln=True)
            pdf.set_font("Helvetica", size=11)
        elif line.startswith('- ') or line.startswith('* '):
            pdf.cell(5)
            pdf.multi_cell(0, 6, "- " + safe_line[2:])
        elif line.strip():
            pdf.multi_cell(0, 6, safe_line)
        else:
            pdf.ln(3)

    buf = io.BytesIO()
    pdf_bytes = pdf.output(dest='S')
    if isinstance(pdf_bytes, str):
        pdf_bytes = pdf_bytes.encode('latin-1')
    buf.write(pdf_bytes)
    buf.seek(0)
    return buf, filename


# ============================================================
# DOCX Generator (with markdown support)
# ============================================================

def generate_docx(content: str, filename: str = "kautilya_artifact.docx",
                  title: str = "Kautilya Export") -> Tuple[io.BytesIO, str]:
    """Generate DOCX from markdown content."""
    try:
        from docx import Document
        from docx.shared import Pt, RGBColor
        from docx.enum.text import WD_PARAGRAPH_ALIGNMENT
    except ImportError:
        raise RuntimeError("python-docx not installed")

    doc = Document()

    # Title
    h = doc.add_heading(title, level=0)

    lines = content.split('\n')
    in_code = False
    code_buffer = []

    for line in lines:
        if line.strip().startswith('```'):
            if in_code:
                # End code block
                code_text = '\n'.join(code_buffer)
                p = doc.add_paragraph()
                run = p.add_run(code_text)
                run.font.name = 'Courier New'
                run.font.size = Pt(9)
                code_buffer = []
                in_code = False
            else:
                in_code = True
            continue

        if in_code:
            code_buffer.append(line)
            continue

        if line.startswith('# '):
            doc.add_heading(line[2:], level=1)
        elif line.startswith('## '):
            doc.add_heading(line[3:], level=2)
        elif line.startswith('### '):
            doc.add_heading(line[4:], level=3)
        elif line.startswith('- ') or line.startswith('* '):
            doc.add_paragraph(line[2:], style='List Bullet')
        elif re.match(r'^\d+\.\s', line):
            doc.add_paragraph(re.sub(r'^\d+\.\s', '', line), style='List Number')
        elif line.strip():
            p = doc.add_paragraph()
            # Handle bold
            parts = re.split(r'(\*\*.+?\*\*)', line)
            for part in parts:
                if part.startswith('**') and part.endswith('**'):
                    run = p.add_run(part[2:-2])
                    run.bold = True
                else:
                    p.add_run(part)
        else:
            doc.add_paragraph()

    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf, filename


# ============================================================
# CSV Generator
# ============================================================

def generate_csv(content: str, filename: str = "kautilya_artifact.csv") -> Tuple[io.BytesIO, str]:
    """Generate CSV from markdown table or JSON array."""
    buf = io.StringIO()
    writer = csv.writer(buf)

    # Try JSON
    try:
        data = json.loads(content) if isinstance(content, str) else content
        if isinstance(data, dict) and 'header' in data and 'rows' in data:
            writer.writerow(data['header'])
            for r in data['rows']:
                writer.writerow(r)
        elif isinstance(data, list) and data and isinstance(data[0], dict):
            keys = list(data[0].keys())
            writer.writerow(keys)
            for d in data:
                writer.writerow([d.get(k, '') for k in keys])
        else:
            raise ValueError
    except (json.JSONDecodeError, TypeError, ValueError):
        # Try markdown table
        tables = parse_markdown_tables(content)
        if tables:
            tbl = tables[0]
            writer.writerow(tbl['header'])
            for r in tbl['rows']:
                writer.writerow(r)
        else:
            # Fallback: each line as a row
            for line in content.split('\n'):
                writer.writerow([line])

    out = io.BytesIO()
    out.write(buf.getvalue().encode('utf-8-sig'))
    out.seek(0)
    return out, filename


# ============================================================
# Markdown Generator (just bytes)
# ============================================================

def generate_markdown(content: str, filename: str = "kautilya_artifact.md") -> Tuple[io.BytesIO, str]:
    """Plain markdown file."""
    buf = io.BytesIO()
    buf.write(content.encode('utf-8'))
    buf.seek(0)
    return buf, filename


# ============================================================
# Dispatcher
# ============================================================

ARTIFACT_GENERATORS = {
    'excel':    generate_excel,
    'xlsx':     generate_excel,
    'pdf':      generate_pdf,
    'docx':     generate_docx,
    'word':     generate_docx,
    'csv':      generate_csv,
    'markdown': generate_markdown,
    'md':       generate_markdown,
}

MIME_TYPES = {
    'excel':    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'xlsx':     'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'pdf':      'application/pdf',
    'docx':     'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'word':     'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'csv':      'text/csv',
    'markdown': 'text/markdown',
    'md':       'text/markdown',
}

DEFAULT_EXTENSIONS = {
    'excel': 'xlsx', 'xlsx': 'xlsx',
    'pdf': 'pdf',
    'docx': 'docx', 'word': 'docx',
    'csv': 'csv',
    'markdown': 'md', 'md': 'md',
}


def create_artifact(kind: str, content: str, title: str = "Kautilya Export",
                    filename: Optional[str] = None) -> Tuple[io.BytesIO, str, str]:
    """Returns (buffer, filename, mimetype). Raises ValueError on bad kind."""
    kind = (kind or '').lower().strip()
    if kind not in ARTIFACT_GENERATORS:
        raise ValueError(f"Unknown artifact kind: {kind}. Supported: {list(ARTIFACT_GENERATORS.keys())}")

    if not filename:
        ext = DEFAULT_EXTENSIONS[kind]
        safe_title = re.sub(r'[^\w\s-]', '', title)[:40].strip().replace(' ', '_') or 'kautilya'
        filename = f"{safe_title}.{ext}"

    gen = ARTIFACT_GENERATORS[kind]
    if kind in ('csv', 'markdown', 'md'):
        buf, fn = gen(content, filename=filename)
    else:
        buf, fn = gen(content, filename=filename, title=title)

    return buf, fn, MIME_TYPES[kind]
