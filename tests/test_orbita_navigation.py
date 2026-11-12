"""Static accessibility and navigation contracts for ORBITA.

Dynamic behavior lives in orbita_ui_sanity.cjs and integration tests.
"""
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class NavigationParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.inside_nav = False
        self.destinations = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == 'nav' and values.get('id') == 'nav':
            self.inside_nav = True
        if tag == 'button' and self.inside_nav and values.get('data-tab'):
            self.destinations.append(values['data-tab'])

    def handle_endtag(self, tag):
        if tag == 'nav':
            self.inside_nav = False


def test_four_primary_destinations():
    parser = NavigationParser()
    parser.feed((ROOT / 'hub/static/index.html').read_text())
    assert parser.destinations == ['today', 'projects', 'events', 'explore']


def test_navigation_and_quick_actions_accessible_without_new_dependencies():
    html = (ROOT / 'hub/static/index.html').read_text()
    js = (ROOT / 'hub/static/orbita-navigation.js').read_text()
    css = (ROOT / 'hub/static/orbita-navigation.css').read_text()
    assert 'href="#content"' in html
    assert 'id="create-open"' in html
    assert 'id="search-open"' in html
    assert 'id="logout"' in html
    for tab in ('tasks','contacts','opportunities','notes','automations'):
        assert f"tab:'{tab}'" in js
    for action in ('add-task','add-note','add-project','add-contact','add-opportunity','add-event'):
        assert f"action:'{action}'" in js
    assert 'env(safe-area-inset-bottom)' in css
    assert 'minmax(0,1fr)' in css
