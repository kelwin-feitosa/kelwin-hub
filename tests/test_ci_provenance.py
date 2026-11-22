"""H17-06/H17-16: guard against mutable GitHub Actions and missing audit triggers."""
from pathlib import Path
import re

WORKFLOWS=Path(__file__).resolve().parents[1]/'.github'/'workflows'


def test_workflow_actions_are_immutable_verified_commit_references():
    for filename in ('quality.yml','browser.yml','a11y.yml','security-audit.yml','codeql.yml'):
        content=(WORKFLOWS/filename).read_text(encoding='utf-8')
        references=re.findall(r'^\s*- uses:\s*([^\s#]+)',content,flags=re.MULTILINE)
        assert references,filename
        assert all(re.fullmatch(r'(?:actions/[a-z0-9-]+|github/codeql-action/(?:init|analyze))@[0-9a-f]{40}',ref)
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


def test_codeql_pinned_to_same_verified_v4_release_sha():
    content=(WORKFLOWS/'codeql.yml').read_text(encoding='utf-8')
    expected='github/codeql-action/'
    sha='1bd86f2fdb4b86187fa4059f16f31a3202acc9ea'
    assert expected+'init@'+sha in content
    assert expected+'analyze@'+sha in content
    assert 'security-events: write' in content
    assert "language:" in content
    assert "'python'" in content
    assert "'javascript-typescript'" in content


def test_quality_collects_real_branch_coverage_and_retains_xml():
    content=(WORKFLOWS/'quality.yml').read_text(encoding='utf-8')
    assert 'python -m coverage run --branch --source=hub -m pytest' in content
    assert 'python -m coverage xml -o coverage.xml' in content
    assert 'name: python-coverage-xml' in content
    assert 'retention-days: 7' in content
    assert 'sonar-scanner' not in content  # Do not configure duplicate Sonar analysis blindly.
    pyproject=(WORKFLOWS.parents[1]/'pyproject.toml').read_text(encoding='utf-8')
    assert 'coverage>=7,<8' in pyproject
