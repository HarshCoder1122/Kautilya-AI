"""
Kautilya AI — Skills Routes Blueprint
Serves the activatable-Skills catalog to the composer's Skills dialog.

The catalog is generated from `skills_spec.py` (single source of truth), so the
cards the user sees and the behaviour the model gets can never drift.
"""
from flask import Blueprint, jsonify

from skills_spec import get_skill_catalog

skills_bp = Blueprint('skills', __name__)


@skills_bp.route('/skills', methods=['GET'])
def list_skills():
    """Public catalog of Skills shown in the composer (metadata only)."""
    skills = get_skill_catalog()
    # Group by category for a tidy dialog, preserving catalog order within groups.
    categories = []
    seen = {}
    for s in skills:
        cat = s.get('category') or 'Other'
        if cat not in seen:
            seen[cat] = {'category': cat, 'skills': []}
            categories.append(seen[cat])
        seen[cat]['skills'].append(s)
    return jsonify({'skills': skills, 'categories': categories, 'total': len(skills)})
