"""
Kautilya AI — Artifact Routes
Generates downloadable Excel, PDF, DOCX, CSV, Markdown files from
markdown text or structured JSON.

POST /api/artifact/create
  body: { kind: "excel"|"pdf"|"docx"|"csv"|"markdown",
          content: "<markdown or JSON>",
          title: "Optional title",
          filename: "Optional filename.ext" }
  returns: file download
"""
from flask import Blueprint, request, jsonify, send_file
from services.artifact_service import create_artifact

artifact_bp = Blueprint('artifact', __name__)


@artifact_bp.route('/api/artifact/create', methods=['POST'])
def api_create_artifact():
    try:
        data = request.get_json(silent=True) or {}
        kind = data.get('kind', 'pdf')
        content = data.get('content', '')
        title = data.get('title', 'Kautilya Export')
        filename = data.get('filename')

        if not content:
            return jsonify({"error": "Missing 'content'"}), 400

        buf, fn, mime = create_artifact(kind, content, title=title, filename=filename)
        return send_file(buf, as_attachment=True, download_name=fn, mimetype=mime)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except RuntimeError as e:
        return jsonify({"error": f"Library missing: {e}"}), 500
    except Exception as e:
        print(f"[Artifact] Failed: {e}")
        return jsonify({"error": str(e)}), 500


@artifact_bp.route('/api/artifact/types', methods=['GET'])
def api_artifact_types():
    """List supported artifact types — used by the UI's slash-command menu."""
    return jsonify({
        "types": [
            {"kind": "excel",    "label": "Excel Spreadsheet", "icon": "table_view",  "ext": "xlsx"},
            {"kind": "pdf",      "label": "PDF Document",      "icon": "picture_as_pdf","ext": "pdf"},
            {"kind": "docx",     "label": "Word Document",     "icon": "description", "ext": "docx"},
            {"kind": "csv",      "label": "CSV File",          "icon": "view_list",   "ext": "csv"},
            {"kind": "markdown", "label": "Markdown",          "icon": "article",     "ext": "md"},
        ]
    })
