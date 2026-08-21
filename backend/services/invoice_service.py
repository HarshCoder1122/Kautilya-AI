"""
Kautilya AI — GST Invoice Service (India 🇮🇳).

A small, *deterministic* engine for Indian SME invoicing:
  • compute_gst()       — CGST/SGST (intra-state) vs IGST (inter-state), per item,
                          rounded to paise. (LLMs are unreliable at arithmetic, so
                          the maths is done in plain Python, never by the model.)
  • extract_invoice()   — pull structured fields out of a pasted/parsed invoice via
                          the LLM (seller, buyer, line items, GSTINs, dates).
  • invoice_to_markdown()/invoice_to_sheet() — render a clean, GST-compliant
                          invoice that the existing artifact engine turns into a
                          branded PDF / DOCX / Excel.

GSTIN format: 2-digit state code + 10-char PAN + 1 entity digit + 'Z' + 1 check
char (15 chars). The first two digits give the place of supply → intra vs inter.
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional


def _f(x, default=0.0) -> float:
    try:
        if isinstance(x, str):
            x = re.sub(r'[^\d.\-]', '', x) or 0
        return round(float(x), 2)
    except Exception:
        return default


def _state_code(gstin: Optional[str], state_fallback: Optional[str] = None) -> Optional[str]:
    """First two digits of a GSTIN = the state code."""
    if gstin and re.match(r'^\d{2}', gstin.strip()):
        return gstin.strip()[:2]
    return None


# Indian numbering → words (for the mandatory "amount in words" line).
_ONES = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine",
         "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen",
         "Seventeen", "Eighteen", "Nineteen"]
_TENS = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]


def _two(n: int) -> str:
    if n < 20:
        return _ONES[n]
    return (_TENS[n // 10] + (" " + _ONES[n % 10] if n % 10 else "")).strip()


def _three(n: int) -> str:
    h, rest = divmod(n, 100)
    out = (_ONES[h] + " Hundred" if h else "")
    if rest:
        out += (" " if out else "") + _two(rest)
    return out


def amount_in_words(amount: float) -> str:
    """Indian-system rupees in words, e.g. 'Rupees One Lakh Twenty Thousand Only'."""
    rupees = int(round(amount))
    paise = int(round((amount - rupees) * 100))
    if rupees == 0:
        words = "Zero"
    else:
        crore, rem = divmod(rupees, 10_000_000)
        lakh, rem = divmod(rem, 100_000)
        thousand, rem = divmod(rem, 1000)
        parts = []
        if crore:
            parts.append(_two(crore) + " Crore")
        if lakh:
            parts.append(_two(lakh) + " Lakh")
        if thousand:
            parts.append(_two(thousand) + " Thousand")
        if rem:
            parts.append(_three(rem))
        words = " ".join(parts)
    out = f"Rupees {words}"
    if paise:
        out += f" and {_two(paise)} Paise"
    return out + " Only"


# ============================================================
# GST computation (deterministic)
# ============================================================

def compute_gst(items: List[Dict[str, Any]],
                seller_gstin: Optional[str] = None,
                buyer_gstin: Optional[str] = None,
                intra_state: Optional[bool] = None,
                default_gst_rate: float = 18.0) -> Dict[str, Any]:
    """Return per-line + summary GST figures.

    intra_state: if None, inferred from GSTIN state codes (same → intra → CGST+SGST;
    different → inter → IGST). Falls back to intra-state when codes are unknown.
    """
    if intra_state is None:
        s, b = _state_code(seller_gstin), _state_code(buyer_gstin)
        intra_state = (s == b) if (s and b) else True

    lines = []
    tot_taxable = tot_cgst = tot_sgst = tot_igst = 0.0
    for it in items:
        qty = _f(it.get('qty', 1) or 1)
        rate = _f(it.get('rate', 0))
        discount = _f(it.get('discount', 0))
        gst_rate = _f(it.get('gst_rate', it.get('gst', default_gst_rate)) or default_gst_rate)
        taxable = round(qty * rate - discount, 2)
        if intra_state:
            cgst = round(taxable * gst_rate / 200.0, 2)   # half each
            sgst = round(taxable * gst_rate / 200.0, 2)
            igst = 0.0
        else:
            cgst = sgst = 0.0
            igst = round(taxable * gst_rate / 100.0, 2)
        line_total = round(taxable + cgst + sgst + igst, 2)
        lines.append({
            'description': str(it.get('description') or it.get('name') or 'Item'),
            'hsn': str(it.get('hsn') or it.get('hsn_sac') or ''),
            'qty': qty, 'unit': str(it.get('unit') or 'Nos'),
            'rate': rate, 'discount': discount,
            'taxable': taxable, 'gst_rate': gst_rate,
            'cgst': cgst, 'sgst': sgst, 'igst': igst, 'total': line_total,
        })
        tot_taxable += taxable
        tot_cgst += cgst
        tot_sgst += sgst
        tot_igst += igst

    grand = round(tot_taxable + tot_cgst + tot_sgst + tot_igst, 2)
    # Round-off to nearest rupee (common on Indian invoices).
    rounded = round(grand)
    round_off = round(rounded - grand, 2)
    return {
        'intra_state': intra_state,
        'lines': lines,
        'subtotal': round(tot_taxable, 2),
        'cgst': round(tot_cgst, 2),
        'sgst': round(tot_sgst, 2),
        'igst': round(tot_igst, 2),
        'total_tax': round(tot_cgst + tot_sgst + tot_igst, 2),
        'grand_total': grand,
        'round_off': round_off,
        'payable': float(rounded),
        'amount_in_words': amount_in_words(float(rounded)),
    }


# ============================================================
# LLM extraction (text → structured fields)
# ============================================================

def extract_invoice(text: str) -> Dict[str, Any]:
    """Parse a pasted/scanned invoice (or a free-text request) into structured
    fields the engine can price. Best-effort; missing fields come back empty."""
    from services.llm_service import call_vertex_gemini
    from services.agent_loop_service import FAST_MODEL
    sys = (
        "Extract invoice data from the user's text into RAW JSON ONLY (no prose, no "
        "markdown). Shape:\n"
        '{ "invoice_no": "", "date": "", "seller": {"name":"","gstin":"","address":"","state":""}, '
        '"buyer": {"name":"","gstin":"","address":"","state":""}, '
        '"items": [{"description":"","hsn":"","qty":1,"unit":"Nos","rate":0,"discount":0,"gst_rate":18}], '
        '"notes": "" }\n'
        "Rules: numbers as numbers (no currency symbols). If a GST rate isn't stated, use 18. "
        "If a field is unknown, use \"\" (or [] for items). Never invent GSTINs."
    )
    try:
        resp = call_vertex_gemini([{"role": "system", "content": sys},
                                   {"role": "user", "content": text.strip()[:6000]}],
                                  model=FAST_MODEL, temperature=0.1,
                                  max_tokens=1500, stream=False)
        if isinstance(resp, str):
            m = re.search(r'\{[\s\S]*\}', resp)
            if m:
                data = json.loads(m.group(0))
                if isinstance(data, dict):
                    data.setdefault('items', [])
                    data.setdefault('seller', {})
                    data.setdefault('buyer', {})
                    return data
    except Exception as e:
        print(f"[Invoice] extract failed: {e}")
    return {"seller": {}, "buyer": {}, "items": [], "notes": ""}


# ============================================================
# Rendering
# ============================================================

def _party_block(label: str, p: Dict[str, Any]) -> str:
    p = p or {}
    out = [f"**{label}:** {p.get('name', '') or '—'}"]
    if p.get('gstin'):
        out.append(f"GSTIN: {p['gstin']}")
    if p.get('address'):
        out.append(p['address'])
    if p.get('state'):
        out.append(f"State: {p['state']}")
    return "  \n".join(out)


def invoice_to_markdown(data: Dict[str, Any], gst: Dict[str, Any]) -> str:
    """Render a GST-compliant Tax Invoice as markdown (fed to the PDF/DOCX engine)."""
    intra = gst['intra_state']
    md = ["# Tax Invoice", ""]
    inv_no = data.get('invoice_no') or '—'
    date = data.get('date') or '—'
    md.append(f"**Invoice No:** {inv_no}  ·  **Date:** {date}")
    md.append("")
    md.append(_party_block("Seller", data.get('seller')))
    md.append("")
    md.append(_party_block("Buyer", data.get('buyer')))
    md.append("")
    md.append(f"**Supply type:** {'Intra-state (CGST + SGST)' if intra else 'Inter-state (IGST)'}")
    md.append("")

    # Line-items table — columns adapt to intra/inter so it stays readable.
    if intra:
        header = "| # | Description | HSN | Qty | Rate | Taxable | CGST | SGST | Total |"
        sep =    "|---|-------------|-----|-----|------|---------|------|------|-------|"
    else:
        header = "| # | Description | HSN | Qty | Rate | Taxable | IGST | Total |"
        sep =    "|---|-------------|-----|-----|------|---------|------|-------|"
    md.append(header)
    md.append(sep)
    for i, ln in enumerate(gst['lines'], 1):
        if intra:
            md.append(f"| {i} | {ln['description']} | {ln['hsn']} | {ln['qty']:g} | "
                      f"{ln['rate']:.2f} | {ln['taxable']:.2f} | {ln['cgst']:.2f} ({ln['gst_rate']/2:g}%) | "
                      f"{ln['sgst']:.2f} ({ln['gst_rate']/2:g}%) | {ln['total']:.2f} |")
        else:
            md.append(f"| {i} | {ln['description']} | {ln['hsn']} | {ln['qty']:g} | "
                      f"{ln['rate']:.2f} | {ln['taxable']:.2f} | {ln['igst']:.2f} ({ln['gst_rate']:g}%) | "
                      f"{ln['total']:.2f} |")
    md.append("")

    # Totals
    md.append(f"**Subtotal (Taxable):** ₹{gst['subtotal']:.2f}")
    if intra:
        md.append(f"**CGST:** ₹{gst['cgst']:.2f}  ·  **SGST:** ₹{gst['sgst']:.2f}")
    else:
        md.append(f"**IGST:** ₹{gst['igst']:.2f}")
    if gst['round_off']:
        md.append(f"**Round-off:** ₹{gst['round_off']:.2f}")
    md.append(f"**Grand Total (Payable):** ₹{gst['payable']:.2f}")
    md.append("")
    md.append(f"**Amount in words:** {gst['amount_in_words']}")
    if data.get('notes'):
        md.append("")
        md.append(f"_Notes: {data['notes']}_")
    md.append("")
    md.append("> This is a computer-generated GST invoice prepared with Kautilya AI. "
              "Verify GSTINs and tax rates before filing.")
    return "\n".join(md)


def invoice_to_sheet(data: Dict[str, Any], gst: Dict[str, Any]) -> Dict[str, Any]:
    """JSON-sheets payload for the Excel generator (one items sheet + a summary)."""
    intra = gst['intra_state']
    if intra:
        header = ["#", "Description", "HSN", "Qty", "Rate", "Taxable", "GST%", "CGST", "SGST", "Total"]
        rows = [[i, l['description'], l['hsn'], l['qty'], l['rate'], l['taxable'],
                 l['gst_rate'], l['cgst'], l['sgst'], l['total']]
                for i, l in enumerate(gst['lines'], 1)]
    else:
        header = ["#", "Description", "HSN", "Qty", "Rate", "Taxable", "GST%", "IGST", "Total"]
        rows = [[i, l['description'], l['hsn'], l['qty'], l['rate'], l['taxable'],
                 l['gst_rate'], l['igst'], l['total']]
                for i, l in enumerate(gst['lines'], 1)]
    summary = [
        ["Subtotal (Taxable)", gst['subtotal']],
        ["CGST", gst['cgst']], ["SGST", gst['sgst']], ["IGST", gst['igst']],
        ["Round-off", gst['round_off']],
        ["Grand Total (Payable)", gst['payable']],
        ["Amount in words", gst['amount_in_words']],
    ]
    return {"sheets": [
        {"name": "Invoice", "header": header, "rows": rows},
        {"name": "Summary", "header": ["Field", "Value"], "rows": summary},
    ]}


def build_invoice(data: Dict[str, Any], default_gst_rate: float = 18.0):
    """Price an invoice from structured `data` and return (data, gst, markdown)."""
    gst = compute_gst(
        data.get('items', []) or [],
        seller_gstin=(data.get('seller') or {}).get('gstin'),
        buyer_gstin=(data.get('buyer') or {}).get('gstin'),
        intra_state=data.get('intra_state'),
        default_gst_rate=default_gst_rate,
    )
    return data, gst, invoice_to_markdown(data, gst)
