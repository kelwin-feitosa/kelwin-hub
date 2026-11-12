"""Static integration guards for an optional, no-framework review UI."""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def test_review_assets_and_explicit_approval():
    html=(ROOT/'hub/static/index.html').read_text()
    js=(ROOT/'hub/static/meeting-review.js').read_text()
    css=(ROOT/'hub/static/meeting-review.css').read_text()
    assert '/static/meeting-review.js' in html and '/static/meeting-review.css' in html
    assert 'KelwinReview.open' in (ROOT/'hub/static/app.js').read_text()
    assert 'navigator.clipboard.writeText' in js
    assert 'Aprovar e criar tarefa' in js
    assert 'meeting-review/items/' in js and 'review-import' in js
    assert 'api(' in js and 'esc(' in js and 'textContent' in js
    assert 'var(--panel)' in css and 'var(--border)' in css


def test_review_private_search_and_explicit_delete():
    js=(ROOT/'hub/static/meeting-review.js').read_text()
    assert "review-delete" in js
    assert "window.confirm" in js
    assert "/api/meeting-review/search?q=" in js
    assert "data-review-trans" in js
