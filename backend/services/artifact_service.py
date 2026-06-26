"""
Kautilya AI — Artifact Service
Generates downloadable artifacts (Excel, PDF, DOCX, CSV, Markdown) from
structured content or markdown text. Used by `/api/artifact/*` routes.

Design note (document beauty):
  Short documents — letters, memos, notes — render CLEAN: no cover page, no
  "Confidential" footer, no auto Table-of-Contents. Just well-typeset content,
  the way Claude exports a one-page letter. The premium cover + TOC + page
  footer is reserved for genuine multi-section REPORTS (research whitepapers),
  where it reads as polish rather than clutter. See `_looks_like_report`.
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
# Shared markdown helpers (inline formatting + structure)
# ============================================================

# Inline-emphasis tokenizer shared by PDF + DOCX. We deliberately support only
# asterisk-based emphasis (not `_..._`) so identifiers and file_names_like_this
# are never accidentally italicised. Order matters: links/code first, then
# bold-italic, bold, italic.
_INLINE_PATTERNS = [
    ('link', re.compile(r'\[([^\]]+)\]\(([^)\s]+)\)')),
    ('code', re.compile(r'`([^`]+)`')),
    ('bi',   re.compile(r'\*\*\*(.+?)\*\*\*')),
    ('b',    re.compile(r'\*\*(.+?)\*\*')),
    ('i',    re.compile(r'(?<!\*)\*(?!\s)(.+?)(?<!\s)\*(?!\*)')),
]


def parse_inline(text: str) -> list:
    """Split a line into styled runs.

    Returns a list of dicts: {'text', 'bold'?, 'italic'?, 'code'?, 'link'?}.
    """
    runs = []
    pos, n = 0, len(text)
    while pos < n:
        best = None
        for kind, rx in _INLINE_PATTERNS:
            m = rx.search(text, pos)
            if m and (best is None or m.start() < best[1].start()):
                best = (kind, m)
        if not best:
            runs.append({'text': text[pos:]})
            break
        kind, m = best
        if m.start() > pos:
            runs.append({'text': text[pos:m.start()]})
        if kind == 'link':
            runs.append({'text': m.group(1), 'link': m.group(2)})
        elif kind == 'code':
            runs.append({'text': m.group(1), 'code': True})
        elif kind == 'bi':
            runs.append({'text': m.group(1), 'bold': True, 'italic': True})
        elif kind == 'b':
            runs.append({'text': m.group(1), 'bold': True})
        elif kind == 'i':
            runs.append({'text': m.group(1), 'italic': True})
        pos = m.end()
    return [r for r in runs if r.get('text')]


def _strip_inline(text: str) -> str:
    """Plain-text version of an inline string (markers removed)."""
    return ''.join(r['text'] for r in parse_inline(text))


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


def _looks_like_report(content: str, headings: list) -> bool:
    """A multi-section report earns the premium cover + TOC + footer treatment.
    Short content (letters, memos, single-topic answers) renders clean."""
    return len(content) > 2600 or len(headings) >= 4


def _is_hr(line: str) -> bool:
    s = line.strip()
    return s in ('---', '***', '___') or bool(re.match(r'^(\*\s*){3,}$|^(-\s*){3,}$|^(_\s*){3,}$', s))


def _logo_path() -> Optional[str]:
    import os
    p = os.path.join(os.path.dirname(__file__), '..', 'static', 'logo.png')
    return p if os.path.exists(p) else None


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
    ' ': ' ', ' ': ' ', '​': '', '﻿': '', '×': 'x',
    '✓': '[ok]', '✔': '[ok]', '✗': '[x]', '✘': '[x]',
    '®': '(R)', '™': '(TM)', '©': '(c)', '°': ' deg',
}

# Candidate Unicode TTFs to embed (installed via Dockerfile: fonts-dejavu-core,
# fonts-noto-core). First hit wins; DejaVu covers Latin/Cyrillic/Greek/₹/symbols,
# Noto adds far broader script coverage (incl. Devanagari for Hindi reports).
_UNICODE_FONT_CANDIDATES = [
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
     "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
     "/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf"),
    ("/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
     "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
     "/usr/share/fonts/truetype/noto/NotoSans-Italic.ttf"),
    ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf", "C:/Windows/Fonts/ariali.ttf"),
    ("C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/segoeuib.ttf", "C:/Windows/Fonts/segoeuii.ttf"),
]


def _register_unicode_font(pdf) -> Optional[str]:
    """Embed the first available Unicode TTF (regular/bold/italic) and return
    its family name, or None if we must fall back to a core (latin-1) font."""
    import os
    for entry in _UNICODE_FONT_CANDIDATES:
        regular, bold = entry[0], entry[1]
        italic = entry[2] if len(entry) > 2 else regular
        if os.path.exists(regular):
            try:
                fam = "UItF"
                pdf.add_font(fam, "", regular)
                pdf.add_font(fam, "B", bold if os.path.exists(bold) else regular)
                pdf.add_font(fam, "I", italic if os.path.exists(italic) else regular)
                pdf.add_font(fam, "BI", bold if os.path.exists(bold) else regular)
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


def generate_pdf(content: str, filename: str = "kautilya_artifact.pdf",
                 title: str = "Kautilya Export") -> Tuple[io.BytesIO, str]:
    """Generate a polished PDF from markdown.

    Long reports get a branded cover page, a clickable table of contents and a
    page-numbered footer. Short documents (letters, memos) render clean — just
    well-typeset content. Inline **bold**/*italic*/`code`/[links] are rendered.
    Uses an embedded Unicode font when available (₹, Hindi, smart quotes…).
    """
    try:
        from fpdf import FPDF
    except ImportError:
        raise RuntimeError("fpdf2 not installed")
    from datetime import datetime

    headings = _collect_headings(content)
    is_report = _looks_like_report(content, headings)

    ACCENT = (0, 82, 255)   # Kautilya brand blue
    INK = (24, 24, 27)
    MUTED = (110, 110, 116)

    class _KautilyaPDF(FPDF):
        def footer(self):
            # Footer only on reports, and never on the cover page.
            if not is_report or getattr(self, 'cover_mode', False):
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
    pdf.set_margins(left=20, top=18, right=20)
    pdf.set_auto_page_break(auto=True, margin=18)

    uni_family = _register_unicode_font(pdf)
    BASE = uni_family or "Helvetica"
    MONO = uni_family or "Courier"
    uni = uni_family is not None
    pdf._base = BASE
    pdf._uni = uni

    def sf(t):
        return _safe(t, uni)

    epw = pdf.w - pdf.l_margin - pdf.r_margin  # effective page width

    def _to_fpdf_md(text):
        """Re-serialise our inline runs into fpdf2's markdown dialect
        (**bold**, __italic__, [text](url)) so multi_cell(markdown=True) wraps
        word-aware AND styles emphasis — no mid-word splits."""
        out = []
        for r in parse_inline(text):
            t = r['text']
            if r.get('link'):
                out.append(f"[{t}]({r['link']})")
            elif r.get('bold') and r.get('italic'):
                out.append(f"**__{t}__**")
            elif r.get('bold'):
                out.append(f"**{t}**")
            elif r.get('italic'):
                out.append(f"__{t}__")
            else:
                out.append(t)  # code & plain → plain text
        return ''.join(out)

    def write_inline(line, height=6.4, bullet=None, indent=0.0):
        """Render one markdown line with bold/italic/links, wrapping cleanly."""
        md = _to_fpdf_md(line)
        if bullet:
            md = f"{bullet}  {md}"
        pdf.set_x(pdf.l_margin + indent)
        pdf.set_font(BASE, '', 11)
        pdf.set_text_color(*INK)
        pdf.multi_cell(epw - indent, height, sf(md), markdown=True,
                       new_x="LMARGIN", new_y="NEXT")

    # ---------------- Cover page (reports only) ----------------
    if is_report:
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
        pdf.set_draw_color(*ACCENT)
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

    # ---------------- Table of contents (clickable, reports only) ----------------
    make_toc = is_report and len(headings) >= 3
    links = []
    if make_toc:
        pdf.add_page()
        pdf.cover_mode = False
        pdf.set_font(BASE, 'B', 16)
        pdf.set_text_color(*INK)
        pdf.cell(0, 10, sf("Contents"), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)
        for _ in headings:
            links.append(pdf.add_link())
        for (level, text), link in zip(headings, links):
            pdf.set_x(pdf.l_margin + (level - 1) * 6)
            pdf.set_font(BASE, 'B' if level == 1 else '', 11 if level == 1 else 10)
            pdf.set_text_color(40, 40, 60)
            pdf.multi_cell(0, 7, sf(_strip_inline(text)), new_x="LMARGIN", new_y="NEXT", link=link)
        pdf.set_text_color(0, 0, 0)
        pdf.add_page()
    else:
        pdf.add_page()
        pdf.cover_mode = False

    # ---------------- Body ----------------
    pdf.set_font(BASE, size=11)
    pdf.set_text_color(*INK)
    heading_idx = 0
    lines = content.split('\n')
    in_code = False
    i = 0

    while i < len(lines):
        line = lines[i]
        pdf.set_x(pdf.l_margin)

        # Code fence
        if line.strip().startswith('```'):
            in_code = not in_code
            i += 1
            continue

        if in_code:
            pdf.set_font(MONO, size=9)
            pdf.set_fill_color(245, 245, 250)
            pdf.set_text_color(40, 40, 50)
            pdf.multi_cell(0, 5, _safe(line, uni), fill=True, new_x="LMARGIN", new_y="NEXT")
            pdf.set_font(BASE, size=11)
            pdf.set_text_color(*INK)
            i += 1
            continue

        # Horizontal rule
        if _is_hr(line):
            pdf.ln(2)
            pdf.set_draw_color(210, 210, 215)
            pdf.set_line_width(0.3)
            y = pdf.get_y()
            pdf.line(pdf.l_margin, y, pdf.w - pdf.r_margin, y)
            pdf.ln(4)
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
                    col_w = epw / col_count
                    pdf.set_font(BASE, 'B', 9)
                    pdf.set_fill_color(*ACCENT)
                    pdf.set_text_color(255, 255, 255)
                    for h in header:
                        pdf.cell(col_w, 7, sf(_strip_inline(h))[:30], border=0, fill=True, align='L')
                    pdf.ln()
                    pdf.set_font(BASE, size=9)
                    pdf.set_text_color(*INK)
                    for ridx, row in enumerate(rows):
                        pdf.set_fill_color(245, 246, 250) if ridx % 2 == 0 else pdf.set_fill_color(255, 255, 255)
                        for ci in range(col_count):
                            val = _strip_inline(row[ci]) if ci < len(row) else ''
                            pdf.cell(col_w, 6.5, sf(val)[:40], border=0, fill=True)
                        pdf.ln()
                    pdf.set_font(BASE, size=11)
                    pdf.ln(3)
            continue

        # Headings
        if line.startswith('# ') or line.startswith('## ') or line.startswith('### '):
            if make_toc and heading_idx < len(links):
                pdf.set_link(links[heading_idx])
                heading_idx += 1
        if line.startswith('# '):
            pdf.ln(2)
            pdf.set_font(BASE, 'B', 17)
            pdf.set_text_color(*INK)
            pdf.multi_cell(0, 9, sf(_strip_inline(line[2:])), new_x="LMARGIN", new_y="NEXT")
            pdf.set_draw_color(*ACCENT); pdf.set_line_width(0.5)
            y = pdf.get_y() + 0.5
            pdf.line(pdf.l_margin, y, pdf.l_margin + 22, y)
            pdf.ln(3)
            pdf.set_font(BASE, size=11)
        elif line.startswith('## '):
            pdf.ln(1.5)
            pdf.set_font(BASE, 'B', 13)
            pdf.set_text_color(*INK)
            pdf.multi_cell(0, 7.5, sf(_strip_inline(line[3:])), new_x="LMARGIN", new_y="NEXT")
            pdf.ln(1)
            pdf.set_font(BASE, size=11)
        elif line.startswith('### '):
            pdf.set_font(BASE, 'B', 11.5)
            pdf.set_text_color(60, 60, 70)
            pdf.multi_cell(0, 6.5, sf(_strip_inline(line[4:])), new_x="LMARGIN", new_y="NEXT")
            pdf.set_text_color(*INK)
            pdf.set_font(BASE, size=11)
        elif line.startswith('> '):
            pdf.set_text_color(*MUTED)
            pdf.set_font(BASE, 'I', 11)
            pdf.set_x(pdf.l_margin + 4)
            pdf.multi_cell(epw - 4, 6.2, sf(_strip_inline(line[2:])), new_x="LMARGIN", new_y="NEXT")
            pdf.set_text_color(*INK)
            pdf.set_font(BASE, size=11)
        elif re.match(r'^\s*[-*+]\s', line):
            content_txt = re.sub(r'^\s*[-*+]\s', '', line)
            depth = (len(line) - len(line.lstrip())) // 2
            write_inline(content_txt, bullet='-', indent=4 + depth * 5)
        elif re.match(r'^\s*\d+\.\s', line):
            num = re.match(r'^\s*(\d+)\.', line).group(1)
            content_txt = re.sub(r'^\s*\d+\.\s', '', line)
            write_inline(content_txt, bullet=f'{num}.', indent=4)
        elif line.strip():
            write_inline(line)
        else:
            pdf.ln(3)

        i += 1

    buf = io.BytesIO()
    try:
        pdf_bytes = pdf.output()
        if isinstance(pdf_bytes, str):
            pdf_bytes = pdf_bytes.encode('latin-1')
    except TypeError:
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
    """Generate a polished DOCX from markdown.

    Long reports get a branded cover page, a Contents page and a page-numbered
    footer. Short documents (letters, memos) render clean — just beautifully
    typeset content (matching how Claude exports a one-page letter). Inline
    **bold**/*italic*/`code`/[links] are rendered as real Word runs.
    """
    try:
        from docx import Document
        from docx.shared import Pt, RGBColor, Inches
        from docx.enum.text import WD_PARAGRAPH_ALIGNMENT, WD_LINE_SPACING
        from docx.oxml.ns import qn
        from docx.oxml import OxmlElement
        from docx.opc.constants import RELATIONSHIP_TYPE
    except ImportError:
        raise RuntimeError("python-docx not installed")
    from datetime import datetime

    CENTER = WD_PARAGRAPH_ALIGNMENT.CENTER
    ACCENT = RGBColor(0x00, 0x52, 0xFF)
    INK = RGBColor(0x1A, 0x1A, 0x1E)
    CODE_CLR = RGBColor(0xC0, 0x39, 0x2B)

    headings = _collect_headings(content)
    is_report = _looks_like_report(content, headings)

    doc = Document()

    # ---- Document-wide typography ----
    normal = doc.styles['Normal']
    normal.font.name = 'Calibri'
    normal.font.size = Pt(11)
    normal.font.color.rgb = INK
    pf = normal.paragraph_format
    pf.line_spacing_rule = WD_LINE_SPACING.MULTIPLE
    pf.line_spacing = 1.15
    pf.space_after = Pt(8)

    # Refine the built-in heading styles so they read modern (not Word-blue).
    for name, size, clr, before, after in [
        ('Heading 1', 18, INK,    14, 6),
        ('Heading 2', 14, INK,    12, 4),
        ('Heading 3', 12, RGBColor(0x3C, 0x3C, 0x46), 10, 3),
    ]:
        try:
            st = doc.styles[name]
            st.font.name = 'Calibri'
            st.font.size = Pt(size)
            st.font.bold = True
            st.font.color.rgb = clr
            st.paragraph_format.space_before = Pt(before)
            st.paragraph_format.space_after = Pt(after)
        except Exception:
            pass

    def _shade(cell, hex_fill):
        tcPr = cell._tc.get_or_add_tcPr()
        shd = OxmlElement('w:shd')
        shd.set(qn('w:val'), 'clear')
        shd.set(qn('w:color'), 'auto')
        shd.set(qn('w:fill'), hex_fill)
        tcPr.append(shd)

    def _add_hyperlink(paragraph, url, text):
        part = paragraph.part
        r_id = part.relate_to(url, RELATIONSHIP_TYPE.HYPERLINK, is_external=True)
        hyperlink = OxmlElement('w:hyperlink')
        hyperlink.set(qn('r:id'), r_id)
        run = OxmlElement('w:r')
        rPr = OxmlElement('w:rPr')
        c = OxmlElement('w:color'); c.set(qn('w:val'), '0052FF'); rPr.append(c)
        u = OxmlElement('w:u'); u.set(qn('w:val'), 'single'); rPr.append(u)
        run.append(rPr)
        t = OxmlElement('w:t'); t.set(qn('xml:space'), 'preserve'); t.text = text
        run.append(t)
        hyperlink.append(run)
        paragraph._p.append(hyperlink)

    def _add_inline(paragraph, text):
        """Add styled runs (bold/italic/code/link) to a paragraph."""
        for r in parse_inline(text):
            if r.get('link'):
                _add_hyperlink(paragraph, r['link'], r['text'])
                continue
            run = paragraph.add_run(r['text'])
            if r.get('bold'):
                run.bold = True
            if r.get('italic'):
                run.italic = True
            if r.get('code'):
                run.font.name = 'Consolas'
                run.font.size = Pt(10)
                run.font.color.rgb = CODE_CLR

    def _add_page_field(paragraph):
        run = paragraph.add_run()
        c1 = OxmlElement('w:fldChar'); c1.set(qn('w:fldCharType'), 'begin')
        instr = OxmlElement('w:instrText'); instr.set(qn('xml:space'), 'preserve'); instr.text = 'PAGE'
        c2 = OxmlElement('w:fldChar'); c2.set(qn('w:fldCharType'), 'end')
        run._r.append(c1); run._r.append(instr); run._r.append(c2)

    # ---- Footer + cover + TOC: reports only ----
    if is_report:
        try:
            fp = doc.sections[0].footer.paragraphs[0]
            fp.alignment = CENTER
            fr = fp.add_run("Kautilya AI   ·   Confidential   ·   Page ")
            fr.font.size = Pt(8); fr.font.color.rgb = RGBColor(0x96, 0x96, 0x96)
            _add_page_field(fp)
        except Exception:
            pass

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
        tr = tp.add_run(title); tr.bold = True; tr.font.size = Pt(26); tr.font.color.rgb = INK
        dp = doc.add_paragraph(); dp.alignment = CENTER
        dr = dp.add_run(datetime.now().strftime('%d %B %Y') + "   ·   Prepared by Kautilya AI")
        dr.font.size = Pt(11); dr.font.color.rgb = RGBColor(0x6e, 0x6e, 0x6e)
        doc.add_page_break()

        if len(headings) >= 3:
            doc.add_heading("Contents", level=1)
            for level, text in headings:
                p = doc.add_paragraph(_strip_inline(text))
                try:
                    p.paragraph_format.left_indent = Inches(0.25 * (level - 1))
                except Exception:
                    pass
                if level == 1:
                    for rr in p.runs:
                        rr.bold = True
            doc.add_page_break()

    # ---- Body ----
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
                p.paragraph_format.left_indent = Inches(0.15)
                run = p.add_run(code_text)
                run.font.name = 'Consolas'
                run.font.size = Pt(9.5)
                run.font.color.rgb = RGBColor(0x2D, 0x2D, 0x37)
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

        # Horizontal rule
        if _is_hr(line):
            p = doc.add_paragraph()
            pPr = p._p.get_or_add_pPr()
            pbdr = OxmlElement('w:pBdr')
            bottom = OxmlElement('w:bottom')
            bottom.set(qn('w:val'), 'single'); bottom.set(qn('w:sz'), '6')
            bottom.set(qn('w:space'), '1'); bottom.set(qn('w:color'), 'CCCCCC')
            pbdr.append(bottom); pPr.append(pbdr)
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
                        cell = hdr_cells[ci]
                        cell.text = ''
                        run = cell.paragraphs[0].add_run(_strip_inline(h))
                        run.bold = True
                        run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
                        _shade(cell, '0052FF')
                    for ri, row in enumerate(rows):
                        row_cells = tbl.rows[ri + 1].cells
                        for ci in range(col_count):
                            cell = row_cells[ci]
                            cell.text = ''
                            _add_inline(cell.paragraphs[0], row[ci] if ci < len(row) else '')
                            if ri % 2 == 1:
                                _shade(cell, 'F4F6FA')
                    doc.add_paragraph()
            continue

        if line.startswith('# '):
            doc.add_heading(_strip_inline(line[2:]), level=1)
        elif line.startswith('## '):
            doc.add_heading(_strip_inline(line[3:]), level=2)
        elif line.startswith('### '):
            doc.add_heading(_strip_inline(line[4:]), level=3)
        elif line.startswith('#### '):
            p = doc.add_paragraph()
            run = p.add_run(_strip_inline(line[5:])); run.bold = True; run.font.size = Pt(11)
        elif line.startswith('> '):
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Inches(0.3)
            _add_inline(p, line[2:])
            for r in p.runs:
                r.italic = True
                r.font.color.rgb = RGBColor(0x55, 0x55, 0x5F)
        elif re.match(r'^\s*[-*+]\s', line):
            p = doc.add_paragraph(style='List Bullet')
            _add_inline(p, re.sub(r'^\s*[-*+]\s', '', line))
        elif re.match(r'^\s*\d+\.\s', line):
            p = doc.add_paragraph(style='List Number')
            _add_inline(p, re.sub(r'^\s*\d+\.\s', '', line))
        elif line.strip():
            p = doc.add_paragraph()
            _add_inline(p, line)
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
# DECK Generators (PowerPoint .pptx + landscape PDF)
# ============================================================
# A "deck" artifact is the JSON the Presentation skill emits and the canvas
# renders live. Both exporters below consume the SAME JSON + theme palette so a
# downloaded PowerPoint / PDF matches the on-screen preview. Theme ids are kept
# in sync with skills_spec.DECK_THEME_IDS and frontend/src/lib/deck.js THEMES.

# theme id → palette dict (hex w/o #). `mesh` = (top-left glow, bottom-right glow)
# used to paint the gradient background in BOTH exporters so a downloaded deck
# matches the on-screen preview. Kept in sync with frontend/src/lib/deck.js THEMES.
_DECK_THEMES = {
    "midnight": {"bg": "0B1020", "surface": "141A2E", "accent": "7C83FF", "accent2": "22D3EE", "text": "F8FAFC", "muted": "9AA6C4", "dark": True,  "mesh": ("1E2A6B", "0A3550")},
    "aurora":   {"bg": "150F2C", "surface": "221645", "accent": "F472B6", "accent2": "A78BFA", "text": "FDF4FF", "muted": "CABDF0", "dark": True,  "mesh": ("5B21B6", "9D174D")},
    "noir":     {"bg": "0B0B0C", "surface": "191919", "accent": "F5F5F5", "accent2": "9CA3AF", "text": "F7F7F7", "muted": "A3A3A3", "dark": True,  "mesh": ("2A2A2C", "1A1A1C")},
    "sunset":   {"bg": "1A100F", "surface": "2C1A16", "accent": "FB7185", "accent2": "FBBF24", "text": "FFF7ED", "muted": "FCC89B", "dark": True,  "mesh": ("9A3412", "9F1239")},
    "emerald":  {"bg": "04302C", "surface": "0A443E", "accent": "34D399", "accent2": "5EEAD4", "text": "ECFDF5", "muted": "86EFC5", "dark": True,  "mesh": ("065F46", "0F766E")},
    "ivory":    {"bg": "F7F5F0", "surface": "FFFFFF", "accent": "1A1A1A", "accent2": "B45309", "text": "1C1917", "muted": "6B6256", "dark": False, "mesh": ("EFE9DC", "FDEBC8")},
    "royal":    {"bg": "1C1840", "surface": "2A235E", "accent": "C4B5FD", "accent2": "FCD34D", "text": "F5F3FF", "muted": "B3A8E6", "dark": True,  "mesh": ("3730A3", "4F46E5")},
}
_DECK_DEFAULT_THEME = "midnight"
DECK_MAX_SLIDES = 20  # user-configurable count, capped here (matches deck.js)


def _parse_deck(content):
    """Tolerant parse of a deck artifact body → dict. Accepts a raw JSON string
    (optionally wrapped in prose/fences) or an already-parsed dict."""
    if isinstance(content, dict):
        data = content
    else:
        s = (content or "").strip()
        # strip a leading ```json / ``` fence if present
        s = re.sub(r'^```[a-zA-Z]*\s*', '', s).strip()
        s = re.sub(r'\s*```$', '', s).strip()
        try:
            data = json.loads(s)
        except (json.JSONDecodeError, TypeError):
            a, b = s.find('{'), s.rfind('}')
            if a < 0 or b <= a:
                raise ValueError("deck content is not valid JSON")
            data = json.loads(s[a:b + 1])
    if not isinstance(data, dict):
        raise ValueError("deck content must be a JSON object")
    slides = data.get('slides')
    if not isinstance(slides, list) or not slides:
        raise ValueError("deck has no slides")
    # Hard ceiling of 20 slides — the user configures the count, but a deck is a
    # visual aid, not a document, so we never render past 20 (matches deck.js).
    if len(slides) > DECK_MAX_SLIDES:
        data['slides'] = slides[:DECK_MAX_SLIDES]
    return data


def _deck_theme(data):
    tid = str(data.get('theme', '') or '').lower().strip()
    return _DECK_THEMES.get(tid, _DECK_THEMES[_DECK_DEFAULT_THEME])


def generate_pptx(content: str, filename: str = "kautilya_deck.pptx",
                  title: str = "Kautilya Deck") -> Tuple[io.BytesIO, str]:
    """Build a real PowerPoint (.pptx) from a deck JSON spec, themed to match the
    live canvas preview. Supports cover/section/bullets/two-column/stats/
    timeline/quote/image/closing layouts."""
    try:
        from pptx import Presentation
        from pptx.util import Inches, Pt, Emu
        from pptx.dml.color import RGBColor
        from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
    except ImportError:
        raise RuntimeError("python-pptx not installed")

    data = _parse_deck(content)
    th = _deck_theme(data)
    bg, surface, accent, accent2, text, muted, is_dark = (
        th['bg'], th['surface'], th['accent'], th['accent2'], th['text'], th['muted'], th['dark'])
    mesh0, mesh1 = th['mesh']
    rgb = lambda h: RGBColor.from_string(h)

    prs = Presentation()
    if str(data.get('aspect', '16:9')) == '4:3':
        prs.slide_width, prs.slide_height = Inches(10), Inches(7.5)
    else:
        prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    SW, SH = prs.slide_width, prs.slide_height
    blank = prs.slide_layouts[6]

    def add_slide():
        s = prs.slides.add_slide(blank)
        r = s.shapes.add_shape(1, 0, 0, SW, SH)  # 1 = rectangle, full-bleed bg
        # Premium gradient background (matches the live preview's mesh). Falls
        # back to a solid fill if this python-pptx build lacks gradient support.
        try:
            r.fill.gradient()
            try:
                r.fill.gradient_angle = 55.0
            except Exception:
                pass
            stops = r.fill.gradient_stops
            stops[0].position = 0.0; stops[0].color.rgb = rgb(mesh0)
            stops[1].position = 1.0; stops[1].color.rgb = rgb(bg)
        except Exception:
            r.fill.solid(); r.fill.fore_color.rgb = rgb(bg)
        r.line.fill.background()
        r.shadow.inherit = False
        return s

    def bar(s, x, y, w, h, color):
        r = s.shapes.add_shape(1, x, y, w, h)
        r.fill.solid(); r.fill.fore_color.rgb = rgb(color)
        r.line.fill.background(); r.shadow.inherit = False
        return r

    def textbox(s, x, y, w, h, runs, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP,
                line_spacing=1.0, space_after=6):
        """runs: list of (text, size, color_hex, bold) — each its own paragraph."""
        tb = s.shapes.add_textbox(x, y, w, h)
        tf = tb.text_frame
        tf.word_wrap = True
        tf.vertical_anchor = anchor
        for i, (t, size, color, bold) in enumerate(runs):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.alignment = align
            p.space_after = Pt(space_after)
            p.line_spacing = line_spacing
            run = p.add_run(); run.text = t
            run.font.size = Pt(size); run.font.bold = bold
            run.font.color.rgb = rgb(color)
            run.font.name = "Calibri"
        return tb

    MX = Inches(0.9)   # content left margin
    CW = SW - MX * 2   # content width

    def _img_stream(url):
        try:
            import requests
            resp = requests.get(url, timeout=6)
            if resp.ok and resp.content:
                return io.BytesIO(resp.content)
        except Exception:
            pass
        return None

    for slide in data['slides']:
        if not isinstance(slide, dict):
            continue
        layout = str(slide.get('layout', 'bullets')).lower().strip()
        s = add_slide()

        if layout in ('cover', 'closing', 'section'):
            # Editorial hero: text left over the gradient, full-bleed image right.
            text_w = CW
            cover_img = _img_stream(slide.get('image', '')) if layout != 'section' else None
            if cover_img:
                iw = Emu(int(SW * 0.42))
                ix = SW - iw
                try:
                    s.shapes.add_picture(cover_img, ix, 0, width=iw, height=SH)
                except Exception:
                    pass
                text_w = ix - MX - Inches(0.4)
            bar(s, MX, Inches(2.55), Inches(1.0), Pt(7), accent)
            runs = []
            eyebrow = slide.get('eyebrow') or slide.get('index') or ''
            if eyebrow:
                runs.append((str(eyebrow).upper(), 14, accent2, True))
            runs.append((str(slide.get('title', title)), 42 if layout != 'section' else 36, text, True))
            if slide.get('subtitle'):
                runs.append((str(slide['subtitle']), 20, muted, False))
            textbox(s, MX, Inches(2.75), text_w, Inches(3.2), runs,
                    anchor=MSO_ANCHOR.TOP, line_spacing=1.08, space_after=14)
            if slide.get('footer'):
                textbox(s, MX, SH - Inches(0.95), text_w, Inches(0.5),
                        [(str(slide['footer']), 12, muted, False)])
            continue

        # ── Header (title + optional kicker) for content slides ──
        top = Inches(0.85)
        bar(s, MX, top + Inches(0.02), Inches(0.55), Pt(5), accent)
        head_runs = []
        if slide.get('subtitle'):
            head_runs.append((str(slide['subtitle']).upper(), 12, accent2, True))
        head_runs.append((str(slide.get('title', '')), 30, text, True))
        textbox(s, MX + Inches(0.75), top - Inches(0.15), CW - Inches(0.75), Inches(1.2),
                head_runs, line_spacing=1.0, space_after=4)
        body_top = Inches(2.25)
        body_h = SH - body_top - Inches(0.7)

        if layout == 'two-column':
            cols = slide.get('columns', [])[:2]
            colw = (CW - Inches(0.5)) / 2
            for ci, col in enumerate(cols):
                cx = MX + ci * (colw + Inches(0.5))
                runs = [(str(col.get('heading', '')), 18, accent2, True)]
                for b in (col.get('bullets') or [])[:6]:
                    runs.append(("•  " + str(b), 15, text, False))
                textbox(s, cx, body_top, colw, body_h, runs, line_spacing=1.1, space_after=8)

        elif layout == 'stats':
            stats = slide.get('stats', [])[:4]
            n = max(1, len(stats))
            gap = Inches(0.4)
            cardw = (CW - gap * (n - 1)) / n
            for i, st in enumerate(stats):
                cx = MX + i * (cardw + gap)
                card = bar(s, cx, body_top, cardw, Inches(2.6), surface)
                card.line.color.rgb = rgb(accent); card.line.width = Pt(1)
                textbox(s, cx, body_top + Inches(0.45), cardw, Inches(1.7), [
                    (str(st.get('value', '')), 40, accent, True),
                    (str(st.get('label', '')), 14, muted, False),
                ], align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, space_after=6)

        elif layout == 'timeline':
            items = slide.get('items', [])[:6]
            n = max(1, len(items))
            rowh = body_h / n
            for i, it in enumerate(items):
                iy = body_top + rowh * i
                bar(s, MX, iy + Pt(4), Inches(0.14), rowh - Pt(10), accent)
                textbox(s, MX + Inches(0.4), iy, CW - Inches(0.4), rowh, [
                    (str(it.get('time', '')), 15, accent2, True),
                    (str(it.get('text', '')), 16, text, False),
                ], anchor=MSO_ANCHOR.MIDDLE, space_after=2)

        elif layout == 'quote':
            textbox(s, MX, body_top, CW, body_h, [
                ("“" + str(slide.get('quote', '')) + "”", 30, text, True),
                ("— " + str(slide.get('author', '')), 16, accent2, False),
            ], anchor=MSO_ANCHOR.MIDDLE, line_spacing=1.15, space_after=18)

        elif layout == 'image':
            img = _img_stream(slide.get('image', ''))
            bullets = slide.get('bullets') or []
            if bullets:
                imgw = CW * 0.52
                if img:
                    try:
                        s.shapes.add_picture(img, MX, body_top, width=imgw, height=body_h)
                    except Exception:
                        bar(s, MX, body_top, imgw, body_h, surface)
                else:
                    bar(s, MX, body_top, imgw, body_h, surface)
                runs = [("•  " + str(b), 16, text, False) for b in bullets[:6]]
                textbox(s, MX + imgw + Inches(0.5), body_top, CW - imgw - Inches(0.5),
                        body_h, runs, line_spacing=1.15, space_after=8)
            else:
                if img:
                    try:
                        s.shapes.add_picture(img, MX, body_top, width=CW, height=body_h)
                    except Exception:
                        bar(s, MX, body_top, CW, body_h, surface)
                else:
                    bar(s, MX, body_top, CW, body_h, surface)
            if slide.get('caption'):
                textbox(s, MX, SH - Inches(0.6), CW, Inches(0.4),
                        [(str(slide['caption']), 11, muted, False)])

        elif layout in ('feature', 'features', 'icons', 'cards'):
            items = (slide.get('features') or slide.get('items') or slide.get('cards') or [])[:4]
            n = max(1, len(items))
            cols = 2 if n >= 4 else n
            rown = (n + cols - 1) // cols
            gap = Inches(0.3)
            cardw = (CW - gap * (cols - 1)) / cols
            cardh = (body_h - gap * (rown - 1)) / rown
            for i, f in enumerate(items):
                cx = MX + (i % cols) * (cardw + gap)
                cy = body_top + (i // cols) * (cardh + gap)
                card = bar(s, cx, cy, cardw, cardh, surface)
                card.line.color.rgb = rgb(accent); card.line.width = Pt(1)
                bar(s, cx + Inches(0.3), cy + Inches(0.3), Inches(0.5), Inches(0.5), accent)
                textbox(s, cx + Inches(0.3), cy + Inches(1.0), cardw - Inches(0.6), cardh - Inches(1.1), [
                    (str(f.get('title', '')), 16, text, True),
                    (str(f.get('text', '')), 12, muted, False),
                ], line_spacing=1.1, space_after=5)

        elif layout in ('process', 'steps'):
            steps = slide.get('steps', [])[:5]
            n = max(1, len(steps))
            gap = Inches(0.3)
            cardw = (CW - gap * (n - 1)) / n
            num_clr = '0B0B12' if is_dark else 'FFFFFF'
            for i, st in enumerate(steps):
                cx = MX + i * (cardw + gap)
                card = bar(s, cx, body_top, cardw, Inches(3.1), surface)
                card.line.color.rgb = rgb(accent); card.line.width = Pt(1)
                badge = bar(s, cx + Inches(0.28), body_top + Inches(0.3), Inches(0.55), Inches(0.55), accent)
                textbox(s, cx + Inches(0.28), body_top + Inches(0.3), Inches(0.55), Inches(0.55),
                        [(str(i + 1), 20, num_clr, True)], align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
                textbox(s, cx + Inches(0.28), body_top + Inches(1.15), cardw - Inches(0.56), Inches(1.7), [
                    (str(st.get('title', '')), 16, text, True),
                    (str(st.get('text', '')), 12, muted, False),
                ], line_spacing=1.1, space_after=6)
                if i < n - 1:
                    textbox(s, cx + cardw - Inches(0.02), body_top + Inches(1.25), gap + Inches(0.04), Inches(0.6),
                            [("→", 24, accent, True)], align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)

        elif layout in ('chart', 'bar', 'bars'):
            ch = slide.get('chart') or slide
            rows = (ch.get('data') or ch.get('bars') or [])[:7]
            mx = max([float(r.get('value', 0) or 0) for r in rows] + [1.0])
            n = max(1, len(rows))
            gap = Inches(0.35)
            colw = (CW - gap * (n - 1)) / n
            base_y = body_top + body_h - Inches(0.5)   # baseline (room for labels)
            max_h = body_h - Inches(1.3)
            for i, r in enumerate(rows):
                cx = MX + i * (colw + gap)
                v = float(r.get('value', 0) or 0)
                bh = Emu(int(max_h * (v / mx) * 0.88)) + Inches(0.12)
                b = bar(s, cx + Emu(int(colw * 0.15)), base_y - bh, Emu(int(colw * 0.7)), bh, accent)
                textbox(s, cx, base_y - bh - Inches(0.42), colw, Inches(0.36),
                        [(str(r.get('value', '')), 14, accent2, True)], align=PP_ALIGN.CENTER)
                textbox(s, cx, base_y + Inches(0.06), colw, Inches(0.4),
                        [(str(r.get('label', '')), 11, muted, False)], align=PP_ALIGN.CENTER)

        else:  # bullets (default)
            runs = [("•  " + str(b), 18, text, False) for b in (slide.get('bullets') or [])[:7]]
            if not runs and slide.get('note'):
                runs = [(str(slide['note']), 18, text, False)]
            textbox(s, MX, body_top, CW, body_h, runs, line_spacing=1.25, space_after=12)

    buf = io.BytesIO()
    prs.save(buf)
    buf.seek(0)
    return buf, filename


def generate_deck_pdf(content: str, filename: str = "kautilya_deck.pdf",
                      title: str = "Kautilya Deck") -> Tuple[io.BytesIO, str]:
    """Landscape PDF of a deck (one slide per page), themed to match the preview.
    A lightweight, dependency-free export so a deck is downloadable as PDF even
    where PowerPoint isn't wanted."""
    try:
        from fpdf import FPDF
    except ImportError:
        raise RuntimeError("fpdf2 not installed")

    data = _parse_deck(content)
    th = _deck_theme(data)
    hx = lambda h: tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    BG, SURF, ACC, ACC2, TXT, MUT = (hx(th['bg']), hx(th['surface']), hx(th['accent']),
                                     hx(th['accent2']), hx(th['text']), hx(th['muted']))
    MESH0, MESH1 = hx(th['mesh'][0]), hx(th['mesh'][1])

    is_43 = str(data.get('aspect', '16:9')) == '4:3'
    W, H = (254, 190.5) if is_43 else (338.7, 190.5)  # mm, 16:9 landscape
    pdf = FPDF(orientation='L', unit='mm', format=(H, W))
    pdf.set_auto_page_break(auto=False)
    uni_family = _register_unicode_font(pdf)
    BASE = uni_family or "Helvetica"
    uni = uni_family is not None
    MX = 18

    def sf(t):
        return _safe(t, uni)

    def fill(c):
        pdf.set_fill_color(*c)

    def _mix(a, b, f):
        return tuple(int(a[i] + (b[i] - a[i]) * f) for i in range(3))

    def page_bg():
        pdf.add_page()
        # Diagonal-ish gradient wash (mesh0 → bg → mesh1 hint) via horizontal
        # slices, so the PDF matches the live preview's premium background.
        steps = 60
        for i in range(steps):
            f = i / (steps - 1)
            top = _mix(MESH0, BG, min(1.0, f * 1.6))           # fade mesh0 out near top
            c = _mix(top, MESH1, max(0.0, (f - 0.55)) * 0.5)    # hint of mesh1 toward bottom
            fill(c); pdf.rect(0, H * i / steps, W + 1, H / steps + 1, style='F')

    def wrapped(txt, x, y, w, size, color, bold=False, lh=1.3, max_lines=None):
        pdf.set_xy(x, y)
        pdf.set_font(BASE, 'B' if bold else '', size)
        pdf.set_text_color(*color)
        pdf.multi_cell(w, size * 0.46 * lh, sf(txt), align='L')
        return pdf.get_y()

    for slide in data['slides']:
        if not isinstance(slide, dict):
            continue
        layout = str(slide.get('layout', 'bullets')).lower().strip()
        page_bg()

        if layout in ('cover', 'closing', 'section'):
            text_w = W - 2 * MX
            if layout != 'section' and slide.get('image'):
                iw = W * 0.42
                try:
                    pdf.image(slide['image'], W - iw, 0, w=iw, h=H)
                except Exception:
                    fill(SURF); pdf.rect(W - iw, 0, iw, H, style='F')
                text_w = (W - iw) - MX - 6
            else:
                fill(SURF); pdf.rect(0, H * 0.82, W, H * 0.18, style='F')
            fill(ACC); pdf.rect(MX, H * 0.33, 22, 2.2, style='F')
            eyebrow = slide.get('eyebrow') or slide.get('index') or ''
            y = H * 0.37
            if eyebrow:
                pdf.set_xy(MX, y); pdf.set_font(BASE, 'B', 12); pdf.set_text_color(*ACC2)
                pdf.cell(0, 6, sf(str(eyebrow).upper())); y += 9
            y = wrapped(str(slide.get('title', title)), MX, y, text_w,
                        34 if layout != 'section' else 28, TXT, bold=True)
            if slide.get('subtitle'):
                wrapped(str(slide['subtitle']), MX, y + 2, text_w, 16, MUT)
            if slide.get('footer'):
                pdf.set_xy(MX, H - 14); pdf.set_font(BASE, '', 10); pdf.set_text_color(*MUT)
                pdf.cell(0, 6, sf(str(slide['footer'])))
            continue

        # content header
        fill(ACC); pdf.rect(MX, 18, 10, 2, style='F')
        if slide.get('subtitle'):
            pdf.set_xy(MX, 22); pdf.set_font(BASE, 'B', 10); pdf.set_text_color(*ACC2)
            pdf.cell(0, 5, sf(str(slide['subtitle']).upper()))
        wrapped(str(slide.get('title', '')), MX, 27, W - 2 * MX, 24, TXT, bold=True)
        by = 52

        if layout == 'two-column':
            cols = slide.get('columns', [])[:2]
            colw = (W - 2 * MX - 12) / 2
            for ci, col in enumerate(cols):
                cx = MX + ci * (colw + 12)
                yy = wrapped(str(col.get('heading', '')), cx, by, colw, 15, ACC2, bold=True)
                for b in (col.get('bullets') or [])[:6]:
                    yy = wrapped("•  " + str(b), cx, yy + 1, colw, 12.5, TXT)
        elif layout == 'stats':
            stats = slide.get('stats', [])[:4]
            n = max(1, len(stats)); gap = 10
            cw = (W - 2 * MX - gap * (n - 1)) / n
            for i, st in enumerate(stats):
                cx = MX + i * (cw + gap)
                fill(SURF); pdf.rect(cx, by, cw, 62, style='F')
                fill(ACC); pdf.rect(cx, by, cw, 2.2, style='F')
                pdf.set_xy(cx, by + 16); pdf.set_font(BASE, 'B', 30); pdf.set_text_color(*ACC)
                pdf.cell(cw, 14, sf(str(st.get('value', ''))), align='C')
                pdf.set_xy(cx, by + 38); pdf.set_font(BASE, '', 11); pdf.set_text_color(*MUT)
                pdf.multi_cell(cw, 5, sf(str(st.get('label', ''))), align='C')
        elif layout == 'timeline':
            items = slide.get('items', [])[:6]
            yy = by
            for it in items:
                fill(ACC); pdf.rect(MX, yy + 1, 3, 12, style='F')
                pdf.set_xy(MX + 7, yy); pdf.set_font(BASE, 'B', 12); pdf.set_text_color(*ACC2)
                pdf.cell(40, 6, sf(str(it.get('time', ''))))
                pdf.set_xy(MX + 7, yy + 6); pdf.set_font(BASE, '', 13); pdf.set_text_color(*TXT)
                yy = pdf.get_y()
                pdf.multi_cell(W - 2 * MX - 7, 6, sf(str(it.get('text', ''))))
                yy = pdf.get_y() + 4
        elif layout == 'quote':
            wrapped("“" + str(slide.get('quote', '')) + "”", MX, by + 10,
                    W - 2 * MX, 26, TXT, bold=True, lh=1.3)
            pdf.set_xy(MX, H - 26); pdf.set_font(BASE, '', 13); pdf.set_text_color(*ACC2)
            pdf.cell(0, 6, sf("— " + str(slide.get('author', ''))))
        elif layout == 'image':
            img = slide.get('image', '')
            iw = (W - 2 * MX) * (0.5 if slide.get('bullets') else 1.0)
            ih = H - by - 24
            try:
                pdf.image(img, MX, by, w=iw, h=ih)
            except Exception:
                fill(SURF); pdf.rect(MX, by, iw, ih, style='F')
            if slide.get('bullets'):
                tx = MX + iw + 10; yy = by
                for b in slide['bullets'][:6]:
                    yy = wrapped("•  " + str(b), tx, yy + 1, W - 2 * MX - iw - 10, 13, TXT)
            if slide.get('caption'):
                pdf.set_xy(MX, H - 16); pdf.set_font(BASE, '', 9); pdf.set_text_color(*MUT)
                pdf.cell(0, 5, sf(str(slide['caption'])))
        elif layout in ('feature', 'features', 'icons', 'cards'):
            items = (slide.get('features') or slide.get('items') or slide.get('cards') or [])[:4]
            n = max(1, len(items)); gap = 8
            cols = 2 if n >= 4 else n
            rown = (n + cols - 1) // cols
            cardw = (W - 2 * MX - gap * (cols - 1)) / cols
            cardh = (H - by - 16 - gap * (rown - 1)) / rown
            for i, f in enumerate(items):
                cx = MX + (i % cols) * (cardw + gap)
                cy = by + (i // cols) * (cardh + gap)
                fill(SURF); pdf.rect(cx, cy, cardw, cardh, style='F')
                fill(ACC); pdf.rect(cx + 9, cy + 9, 13, 13, style='F')
                yy = wrapped(str(f.get('title', '')), cx + 9, cy + 28, cardw - 18, 14, TXT, bold=True)
                if f.get('text'):
                    wrapped(str(f.get('text', '')), cx + 9, yy + 1, cardw - 18, 11, MUT)

        elif layout in ('process', 'steps'):
            steps = slide.get('steps', [])[:5]
            n = max(1, len(steps)); gap = 8
            cardw = (W - 2 * MX - gap * (n - 1)) / n
            cardh = H - by - 16
            num_clr = (11, 11, 18) if th['dark'] else (255, 255, 255)
            arrow = '→' if uni else '>'
            for i, st in enumerate(steps):
                cx = MX + i * (cardw + gap)
                fill(SURF); pdf.rect(cx, by, cardw, cardh, style='F')
                fill(ACC); pdf.rect(cx, by, cardw, 2, style='F')
                fill(ACC); pdf.rect(cx + 8, by + 10, 13, 13, style='F')
                pdf.set_xy(cx + 8, by + 11.5); pdf.set_font(BASE, 'B', 13); pdf.set_text_color(*num_clr)
                pdf.cell(13, 10, sf(str(i + 1)), align='C')
                yy = wrapped(str(st.get('title', '')), cx + 8, by + 32, cardw - 16, 14, TXT, bold=True)
                wrapped(str(st.get('text', '')), cx + 8, yy + 1, cardw - 16, 11, MUT)
                if i < n - 1:
                    pdf.set_xy(cx + cardw - 1, by + cardh / 2 - 5); pdf.set_font(BASE, 'B', 18)
                    pdf.set_text_color(*ACC); pdf.cell(gap + 2, 10, sf(arrow), align='C')

        elif layout in ('chart', 'bar', 'bars'):
            ch = slide.get('chart') or slide
            rows = (ch.get('data') or ch.get('bars') or [])[:7]
            mx = max([float(r.get('value', 0) or 0) for r in rows] + [1.0])
            n = max(1, len(rows)); gap = 10
            colw = (W - 2 * MX - gap * (n - 1)) / n
            base = H - 28; maxh = base - by - 16
            for i, r in enumerate(rows):
                cx = MX + i * (colw + gap)
                v = float(r.get('value', 0) or 0)
                bh = max(4.0, maxh * (v / mx) * 0.9)
                fill(ACC); pdf.rect(cx + colw * 0.12, base - bh, colw * 0.76, bh, style='F')
                pdf.set_xy(cx, base - bh - 8); pdf.set_font(BASE, 'B', 12); pdf.set_text_color(*ACC2)
                pdf.cell(colw, 6, sf(str(r.get('value', ''))), align='C')
                pdf.set_xy(cx, base + 3); pdf.set_font(BASE, '', 10); pdf.set_text_color(*MUT)
                pdf.multi_cell(colw, 5, sf(str(r.get('label', ''))), align='C')

        else:  # bullets
            yy = by
            blts = slide.get('bullets') or ([slide['note']] if slide.get('note') else [])
            for b in blts[:7]:
                yy = wrapped("•  " + str(b), MX, yy + 2, W - 2 * MX, 15, TXT, lh=1.25)

    buf = io.BytesIO()
    out = pdf.output()
    if isinstance(out, str):
        out = out.encode('latin-1')
    buf.write(bytes(out))
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
    'pptx':     generate_pptx,
    'ppt':      generate_pptx,
    'deck':     generate_pptx,      # default deck export = PowerPoint
    'deck_pdf': generate_deck_pdf,  # deck → landscape PDF
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
    'pptx':     'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    'ppt':      'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    'deck':     'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    'deck_pdf': 'application/pdf',
}

DEFAULT_EXTENSIONS = {
    'excel': 'xlsx', 'xlsx': 'xlsx',
    'pdf': 'pdf',
    'docx': 'docx', 'word': 'docx',
    'csv': 'csv',
    'markdown': 'md', 'md': 'md',
    'pptx': 'pptx', 'ppt': 'pptx', 'deck': 'pptx', 'deck_pdf': 'pdf',
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
