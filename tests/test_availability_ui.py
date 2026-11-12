from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def test_private_availability_ui_integration():
    html=(ROOT/'hub/static/index.html').read_text()
    ui=(ROOT/'hub/static/availability-ui.js').read_text()
    base=(ROOT/'hub/static/app.js').read_text()
    css=(ROOT/'hub/static/availability-ui.css').read_text()
    assert '/static/availability-ui.js' in html
    assert '/static/availability-ui.css' in html
    assert 'KelwinAvailability.open' in base
    assert 'availability-open' in base
    assert '/api/availability/windows' in ui
    assert '/api/availability/slots' in ui
    assert "'/api/events','POST'" in ui
    assert 'var(--panel)' in css
