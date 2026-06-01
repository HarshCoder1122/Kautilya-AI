"""
Kautilya AI — GST Invoice Routes 🇮🇳

POST /api/invoice/extract   { text }                     → structured fields (JSON)
POST /api/invoice/compute   { data | text }              → priced invoice + markdown
POST /api/invoice/generate  { data | text, kind, ... }   → downloadable invoice file

`kind`: pdf | docx | excel  (default pdf). Tax maths is deterministic (server-side),
never the model — see services/invoice_service.compute_gst.
"""
import json

from flask import Blueprint, request, jsonify, send_file

from services.auth_service import verify_firebase_token
from services.invoice_service import extract_invoice, build_invoice, invoice_to_sheet

invoice_bp = Blueprint('invoice', __name__)


def _resolve_data(payload):
    """Return structured invoice data — from `data`, or extracted from `text`."""
    data = payload.get('data')
    if isinstance(data, dict) and data.get('items'):
        return data
    text = (payload.get('text') or payload.get('message') or '').strip()
    if text:
        return extract_invoice(text)
    return data if isinstance(data, dict) else None


@invoice_bp.route('/invoice/extract', methods=['POST'])
def api_invoice_extract():
    token = verify_firebase_token()
    if not token or not token.get('uid'):
        return jsonify({"error": "Unauthorized"}), 401
    payload = request.get_json(silent=True) or {}
    text = (payload.get('text') or payload.get('message') or '').strip()
    if not text:
        return jsonify({"error": "Missing 'text'"}), 400
    return jsonify({"data": extract_invoice(text)})


@invoice_bp.route('/invoice/compute', methods=['POST'])
def api_invoice_compute():
    token = verify_firebase_token()
    if not token or not token.get('uid'):
        return jsonify({"error": "Unauthorized"}), 401
    payload = request.get_json(silent=True) or {}
    data = _resolve_data(payload)
    if not data or not data.get('items'):
        return jsonify({"error": "No invoice items found. Provide 'data' with items or 'text' to parse."}), 400
    rate = float(payload.get('default_gst_rate', 18) or 18)
    data, gst, markdown = build_invoice(data, default_gst_rate=rate)
    return jsonify({"data": data, "gst": gst, "markdown": markdown})


@invoice_bp.route('/invoice/generate', methods=['POST'])
def api_invoice_generate():
    token = verify_firebase_token()
    if not token or not token.get('uid'):
        return jsonify({"error": "Unauthorized"}), 401
    payload = request.get_json(silent=True) or {}
    data = _resolve_data(payload)
    if not data or not data.get('items'):
        return jsonify({"error": "No invoice items found. Provide 'data' with items or 'text' to parse."}), 400

    rate = float(payload.get('default_gst_rate', 18) or 18)
    kind = (payload.get('kind') or 'pdf').lower().strip()
    data, gst, markdown = build_invoice(data, default_gst_rate=rate)

    inv_no = (data.get('invoice_no') or 'invoice')
    safe = ''.join(c for c in str(inv_no) if c.isalnum() or c in '-_') or 'invoice'
    title = f"Tax Invoice {data.get('invoice_no', '')}".strip()

    try:
        from services.artifact_service import create_artifact
        if kind in ('excel', 'xlsx'):
            content = json.dumps(invoice_to_sheet(data, gst))
        else:
            content = markdown
        buf, fn, mime = create_artifact(kind, content, title=title or "Tax Invoice",
                                        filename=f"{safe}.{ 'xlsx' if kind in ('excel','xlsx') else kind}")
        return send_file(buf, as_attachment=True, download_name=fn, mimetype=mime)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except RuntimeError as e:
        return jsonify({"error": f"Library missing: {e}"}), 500
    except Exception as e:
        print(f"[Invoice] generate failed: {e}")
        return jsonify({"error": str(e)}), 500
