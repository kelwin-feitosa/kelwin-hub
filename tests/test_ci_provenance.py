"""H17-06/H17-16: guard against mutable GitHub Actions and missing audit triggers."""
from pathlib import Path
import re

WORKFLOWS=Path(__file__).resolve().parents[1]/'.github'/'workflows'


def test_workflow_actions_are_immutable_verified_commit_references():
    for filename in ('quality.yml','browser.yml','a11y.yml','security-audit.yml'):
        content=(WORKFLOWS/filename).read_text(encoding='utf-8')
        references=re.findall(r'^\s*- uses:\s*([^\s#]+)',content,flags=re.MULTILINE)
        assert references,filename
        assert all(re.fullmatch(r'actions/[a-z0-9-]+@[0-9a-f]{40}',ref)
                   for ref in references), (filename,references)


def test_security_audit_tracks_python_sources_and_code_changes():
    content=(WORKFLOWS/'security-audit.yml').read_text(encoding='utf-8')
    for block in ('pull_request:', 'push:', "      - 'hub/**'",
                  "      - 'scripts/**'", "      - 'tests/**'",
                  "      - 'pyproject.toml'", "      - '.github/workflows/**'"):
        assert block in content, block
    # Both PR and main push paths must match; tests/scripts changes may affect runtime.
    assert content.count("      - 'scripts/**'")==2
    assert content.count("      - 'tests/**'")==2


def test_workflow_has_read_only_github_token():
    for file in ('quality.yml','browser.yml','a11y.yml','security-audit.yml'):
        text=(WORKFLOWS/file).read_text(encoding='utf-8')
        assert 'permissions:\n  contents: read' in text,file
