import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def test_n8n_template_json_structure():
    doc=json.loads((ROOT/'workflows/stale-opportunities-n8n.json').read_text())
    names={node['name'] for node in doc['nodes']}
    assert 'A cada 6 horas' in names and 'Executar no Hub' in names
    assert doc['active'] is False
    assert 'http://hub:8000/api/internal/automations/stale_opportunities/run' in (ROOT/'workflows/stale-opportunities-n8n.json').read_text()


def test_local_by_default_no_secrets_in_release():
    compose=(ROOT/'compose.yaml').read_text()
    assert '127.0.0.1:8000:8000' in compose
    assert '0.0.0.0:8000' not in compose
    assert not (ROOT/'.env').exists()
    assert (ROOT/'.gitignore').read_text().splitlines()[0] == '.env'
