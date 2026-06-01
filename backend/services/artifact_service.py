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

# Common Unicode → ASCII fallbacks so a core-font PDF stays readable even
# when no Unicode TTF is available (smart quotes, dashes, bullets, ₹, etc.).
_TRANSLITERATE = {
    '₹': 'Rs.', '€': 'EUR', '£': 'GBP', '¥': 'JPY',
    '‘': "'", '’': "'", '“': '"', '”': '"',
    '–': '-', '—': '-', '−': '-', '…': '...',
    '•': '*', '‣': '*', '●': '*', '▪': '*', '·': '*',
    '→': '->', '←': '<-', '⇒': '=>', '≤': '<=', '≥': '>=',
    ' ': ' ', ' ': ' ', '​': '', '﻿': '', '×': 'x',
    '✓': '[ok]', '✔': '[ok]', '✗': '[x]', '✘': '[x]',
    '®': '(R)', '™': '(TM)', '©': '(c)', '°': ' deg',
}

# Candidate Unicode TTFs to embed (installed via Dockerfile: fonts-dejavu-core,
# fonts-noto-core). First hit wins; DejaVu covers Latin/Cyrillic/Greek/₹/symbols,
# Noto adds far broader script coverage (incl. Devanagari for Hindi reports).
_UNICODE_FONT_CANDIDATES = [
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
     "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ("/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
     "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf"),
    ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"),
    ("C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/segoeuib.ttf"),
]


def _register_unicode_font(pdf) -> Optional[str]:
    """Embed the first available Unicode TTF and return its family name, or
    None if we must fall back to a core (latin-1) font."""
    import os
    for regular, bold in _UNICODE_FONT_CANDIDATES:
        if os.path.exists(regular):
            try:
                fam = "UItF"
                pdf.add_font(fam, "", regular)
                pdf.add_font(fam, "B", bold if os.path.exists(bold) else regular)
                return fam
            except Exception:
                continue
    return None


def _safe(text: str, uni: bool = False) -> str:
    """Make text PDF-safe. With a Unicode font (uni=True) we pass text through
    untouched; with a core font we transliterate then drop anything non-latin-1
    so we never emit '?' garbage for ₹ / smart quotes / dashes."""
    s = str(text)
    if uni:
        return s
    for k, v in _TRANSLITERATE.items():
        if k in s:
            s = s.replace(k, v)
    return s.encode('latin-1', 'replace').decode('latin-1')


def _collect_headings(content: str) -> list:
    """Ordered list of (level, text) for #/##/### headings, skipping code."""
    heads = []
    in_code = False
    for line in content.split('\n'):
        if line.strip().startswith('```'):
            in_code = not in_code
            continue
        if in_code:
            continue
        if line.startswith('### '):
            heads.append((3, line[4:].strip()))
        elif line.startswith('## '):
            heads.append((2, line[3:].strip()))
        elif line.startswith('# '):
            heads.append((1, line[2:].strip()))
    return heads


def _logo_path() -> Optional[str]:
    import os
    p = os.path.join(os.path.dirname(__file__), '..', 'static', 'logo.png')
    return p if os.path.exists(p) else None


def generate_pdf(content: str, filename: str = "kautilya_artifact.pdf",
                 title: str = "Kautilya Export") -> Tuple[io.BytesIO, str]:
    """Generate a BRANDED PDF from markdown: cover page (logo + title + date),
    a clickable table of contents, footer with page numbers, then the body.

    Uses an embedded Unicode font when available (₹, Hindi, smart quotes…),
    else falls back to the core Helvetica font with transliteration.
    """
    try:
        from fpdf import FPDF
    except ImportError:
        raise RuntimeError("fpdf2 not installed")
    from datetime import datetime

    class _KautilyaPDF(FPDF):
        def footer(self):
            # No footer on the cover page.
            if getattr(self, 'cover_mode', False):
                return
            try:
                self.set_y(-12)
                self.set_font(self._base, '', 8)
                self.set_text_color(150, 150, 150)
                label = f"Kautilya AI   ·   Confidential   ·   Page {self.page_no()}"
                self.cell(0, 8, _safe(label, self._uni), align='C')
                self.set_text_color(0, 0, 0)
            except Exception:
                pass

    pdf = _KautilyaPDF()
    pdf.set_auto_page_break(auto=True, margin=18)

    uni_family = _register_unicode_font(pdf)
    BASE = uni_family or "Helvetica"
    MONO = uni_family or "Courier"
    uni = uni_family is not None
    pdf._base = BASE
    pdf._uni = uni

    def sf(t):
        return _safe(t, uni)

    # ---------------- Cover page ----------------
    pdf.cover_mode = True
    pdf.add_page()
    logo = _logo_path()
    if logo:
        try:
            lw = 32
            pdf.image(logo, x=(pdf.w - lw) / 2, y=48, w=lw)
        except Exception:
            pass
    pdf.set_y(92)
    pdf.set_font(BASE, 'B', 10)
    pdf.set_text_color(130, 130, 130)
    pdf.cell(0, 7, sf("KAUTILYA  AI"), align='C', new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)
    pdf.set_text_color(20, 20, 24)
    pdf.set_font(BASE, 'B', 24)
    pdf.multi_cell(0, 12, sf(title), align='C')
    pdf.ln(8)
    pdf.set_draw_color(79, 70, 229)
    pdf.set_line_width(0.8)
    cx = pdf.w / 2
    pdf.line(cx - 18, pdf.get_y(), cx + 18, pdf.get_y())
    pdf.ln(8)
    pdf.set_font(BASE, '', 12)
    pdf.set_text_color(110, 110, 110)
    pdf.cell(0, 7, sf(datetime.now().strftime('%d %B %Y')), align='C', new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1)
    pdf.cell(0, 7, sf("Prepared by Kautilya AI"), align='C', new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)

    # ---------------- Table of contents (clickable) ----------------
    headings = _collect_headings(content)
    make_toc = len(headings) >= 3
    links = []
    if make_toc:
        pdf.add_page()             # footer fires for cover → cover_mode True → skipped
        pdf.cover_mode = False
        pdf.set_font(BASE, 'B', 16)
        pdf.cell(0, 10, sf("Contents"), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)
        for _ in headings:
            links.append(pdf.add_link())
        for (level, text), link in zip(headings, links):
            pdf.set_x(pdf.l_margin + (level - 1) * 6)
            pdf.set_font(BASE, 'B' if level == 1 else '', 11 if level == 1 else 10)
            pdf.set_text_color(40, 40, 60)
            pdf.multi_cell(0, 7, sf(text), new_x="LMARGIN", new_y="NEXT", link=link)
        pdf.set_text_color(0, 0, 0)
        pdf.add_page()             # start body on a fresh page
    else:
        pdf.add_page()             # leave cover, start body
        pdf.cover_mode = False

    # Body — parse simple markdown
    pdf.set_font(BASE, size=11)
    heading_idx = 0
    lines = content.split('\n')
    in_code = False
    i = 0

    while i < len(lines):
        line = lines[i]
        safe_line = sf(line)
        # fpdf2's multi_cell default leaves the cursor at the RIGHT margin, so a
        # following multi_cell(w=0) would get zero usable width and raise. Reset
        # to the left margin at the top of every block to guarantee full width.
        pdf.set_x(pdf.l_margin)

        # Code fence
        if line.strip().startswith('```'):
            in_code = not in_code
            if in_code:
                pdf.set_font(MONO, size=9)
            else:
                pdf.set_font(BASE, size=11)
            i += 1
            continue

        if in_code:
            pdf.set_fill_color(245, 245, 250)
            pdf.multi_cell(0, 5, safe_line, fill=True)
            i += 1
            continue

        # Markdown table: collect all consecutive table rows
        if '|' in line and line.strip().startswith('|'):
            table_lines = []
            while i < len(lines) and '|' in lines[i] and lines[i].strip().startswith('|'):
                table_lines.append(lines[i])
                i += 1
            # Parse header + separator + rows
            if len(table_lines) >= 2:
                parse_row = lambda r: [c.strip() for c in r.strip().strip('|').split('|')]
                header = parse_row(table_lines[0])
                # skip separator line (---)
                data_start = 1
                if len(table_lines) > 1 and re.match(r'^\|?[\s\-:|]+\|', table_lines[1]):
                    data_start = 2
                rows = [parse_row(r) for r in table_lines[data_start:]]

                col_count = len(header)
                if col_count > 0:
                    page_w = pdf.w - pdf.l_margin - pdf.r_margin
                    col_w = page_w / col_count

                    # Header row
                    pdf.set_font(BASE, 'B', 9)
                    pdf.set_fill_color(79, 70, 229)
                    pdf.set_text_color(255, 255, 255)
                    for h in header:
                        pdf.cell(col_w, 7, sf(h)[:30], border=1, fill=True)
                    pdf.ln()

                    # Data rows
                    pdf.set_font(BASE, size=9)
                    pdf.set_text_color(0, 0, 0)
                    for ridx, row in enumerate(rows):
                        if ridx % 2 == 0:
                            pdf.set_fill_color(245, 245, 250)
                        else:
                            pdf.set_fill_color(255, 255, 255)
                        for ci, cell in enumerate(row[:col_count]):
                            pdf.cell(col_w, 6, sf(cell)[:40], border=1, fill=True)
                        # pad missing columns
                        for _ in range(col_count - len(row)):
                            pdf.cell(col_w, 6, '', border=1, fill=True)
                        pdf.ln()

                    pdf.set_font(BASE, size=11)
                    pdf.ln(3)
            continue

        # Headings — multi_cell (not cell) so long headings wrap instead of
        # throwing "Not enough horizontal space". Anchor the TOC link here so
        # clicking a Contents entry jumps to the section.
        if line.startswith('# ') or line.startswith('## ') or line.startswith('### '):
            if make_toc and heading_idx < len(links):
                pdf.set_link(links[heading_idx])
                heading_idx += 1
        if line.startswith('# '):
            pdf.set_font(BASE, 'B', 14)
            pdf.multi_cell(0, 8, sf(line[2:]), new_x="LMARGIN", new_y="NEXT")
            pdf.set_font(BASE, size=11)
            pdf.ln(1)
        elif line.startswith('## '):
            pdf.set_font(BASE, 'B', 12)
            pdf.multi_cell(0, 7, sf(line[3:]), new_x="LMARGIN", new_y="NEXT")
            pdf.set_font(BASE, size=11)
        elif line.startswith('### '):
            pdf.set_font(BASE, 'B', 11)
            pdf.multi_cell(0, 6, sf(line[4:]), new_x="LMARGIN", new_y="NEXT")
            pdf.set_font(BASE, size=11)
        elif line.startswith('- ') or line.startswith('* '):
            clean = re.sub(r'\*{1,3}(.+?)\*{1,3}', r'\1', line[2:])
            pdf.multi_cell(0, 6, sf('• ' + clean))
        elif re.match(r'^\d+\.\s', line):
            clean = re.sub(r'\*{1,3}(.+?)\*{1,3}', r'\1', line)
            pdf.multi_cell(0, 6, sf(clean))
        elif line.strip():
            # Strip inline markdown bold/italic markers
            clean = re.sub(r'\*{1,3}(.+?)\*{1,3}', r'\1', line)
            pdf.multi_cell(0, 6, sf(clean))
        else:
            pdf.ln(3)

        i += 1

    buf = io.BytesIO()
    try:
        # fpdf2 >= 2.x: output() returns bytes
        pdf_bytes = pdf.output()
        if isinstance(pdf_bytes, str):
            pdf_bytes = pdf_bytes.encode('latin-1')
    except TypeError:
        # older fpdf fallback
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
    """Generate a BRANDED DOCX from markdown: cover page (logo + title + date),
    a Contents page, a page-numbered footer, then the body."""
    try:
        from docx import Document
        from docx.shared import Pt, RGBColor, Inches
        from docx.enum.text import WD_PARAGRAPH_ALIGNMENT
        from docx.oxml.ns import qn
        from docx.oxml import OxmlElement
    except ImportError:
        raise RuntimeError("python-docx not installed")
    from datetime import datetime

    CENTER = WD_PARAGRAPH_ALIGNMENT.CENTER

    def _add_page_field(paragraph):
        """Insert a live Word PAGE number field into a paragraph."""
        run = paragraph.add_run()
        c1 = OxmlElement('w:fldChar'); c1.set(qn('w:fldCharType'), 'begin')
        instr = OxmlElement('w:instrText'); instr.set(qn('xml:space'), 'preserve'); instr.text = 'PAGE'
        c2 = OxmlElement('w:fldChar'); c2.set(qn('w:fldCharType'), 'end')
        run._r.append(c1); run._r.append(instr); run._r.append(c2)

    doc = Document()

    # ---- Footer: brand + page number (every page) ----
    try:
        fp = doc.sections[0].footer.paragraphs[0]
        fp.alignment = CENTER
        fr = fp.add_run("Kautilya AI   ·   Confidential   ·   Page ")
        fr.font.size = Pt(8); fr.font.color.rgb = RGBColor(0x96, 0x96, 0x96)
        _add_page_field(fp)
    except Exception:
        pass

    # ---- Cover page ----
    logo = _logo_path()
    if logo:
        try:
            pic_p = doc.add_paragraph(); pic_p.alignment = CENTER
            pic_p.add_run().add_picture(logo, width=Inches(1.3))
        except Exception:
            pass
    bp = doc.add_paragraph(); bp.alignment = CENTER
    br = bp.add_run("KAUTILYA AI"); br.bold = True; br.font.size = Pt(11)
    br.font.color.rgb = RGBColor(0x82, 0x82, 0x82)
    tp = doc.add_paragraph(); tp.alignment = CENTER
    tr = tp.add_run(title); tr.bold = True; tr.font.size = Pt(26)
    dp = doc.add_paragraph(); dp.alignment = CENTER
    dr = dp.add_run(datetime.now().strftime('%d %B %Y') + "   ·   Prepared by Kautilya AI")
    dr.font.size = Pt(11); dr.font.color.rgb = RGBColor(0x6e, 0x6e, 0x6e)
    doc.add_page_break()

    # ---- Contents (when the doc has enough sections) ----
    headings = _collect_headings(content)
    if len(headings) >= 3:
        doc.add_heading("Contents", level=1)
        for level, text in headings:
            p = doc.add_paragraph(text)
            try:
                p.paragraph_format.left_indent = Inches(0.25 * (level - 1))
            except Exception:
                pass
            if level == 1:
                for rr in p.runs:
                    rr.bold = True
        doc.add_page_break()

    lines = content.split('\n')
    in_code = False
    code_buffer = []
    i = 0

    while i < len(lines):
        line = lines[i]

        if line.strip().startswith('```'):
            if in_code:
                code_text = '\n'.join(code_buffer)
                p = doc.add_paragraph()
                run = p.add_run(code_text)
                run.font.name = 'Courier New'
                run.font.size = Pt(9)
                code_buffer = []
                in_code = False
            else:
                in_code = True
            i += 1
            continue

        if in_code:
            code_buffer.append(line)
            i += 1
            continue

        # Markdown table
        if '|' in line and line.strip().startswith('|'):
            table_lines = []
            while i < len(lines) and '|' in lines[i] and lines[i].strip().startswith('|'):
                table_lines.append(lines[i])
                i += 1
            if len(table_lines) >= 2:
                parse_row = lambda r: [c.strip() for c in r.strip().strip('|').split('|')]
                header = parse_row(table_lines[0])
                data_start = 1
                if len(table_lines) > 1 and re.match(r'^\|?[\s\-:|]+\|', table_lines[1]):
                    data_start = 2
                rows = [parse_row(r) for r in table_lines[data_start:]]
                col_count = len(header)
                if col_count > 0:
                    tbl = doc.add_table(rows=1 + len(rows), cols=col_count)
                    tbl.style = 'Table Grid'
                    hdr_cells = tbl.rows[0].cells
                    for ci, h in enumerate(header):
                        hdr_cells[ci].text = h
                        run = hdr_cells[ci].paragraphs[0].runs[0] if hdr_cells[ci].paragraphs[0].runs else hdr_cells[ci].paragraphs[0].add_run(h)
                        run.bold = True
                    for ri, row in enumerate(rows):
                        row_cells = tbl.rows[ri + 1].cells
                        for ci in range(col_count):
                            row_cells[ci].text = row[ci] if ci < len(row) else ''
                    doc.add_paragraph()
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
            parts = re.split(r'(\*\*.+?\*\*)', line)
            for part in parts:
                if part.startswith('**') and part.endswith('**'):
                    run = p.add_run(part[2:-2])
                    run.bold = True
                else:
                    p.add_run(part)
        else:
            doc.add_paragraph()

        i += 1

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
