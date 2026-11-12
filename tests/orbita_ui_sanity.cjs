const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
const html = fs.readFileSync(path.join(root, 'hub/static/index.html'), 'utf8');
const css = fs.readFileSync(path.join(root, 'hub/static/orbita-navigation.css'), 'utf8');
const source = fs.readFileSync(path.join(root, 'hub/static/orbita-navigation.js'), 'utf8');
const view = {innerHTML: ''};
const ctx = vm.createContext({
  window: {addEventListener() {}},
  document: {getElementById(id) {return id === 'content' ? view : null;}},
});
vm.runInContext(source, ctx, {filename:'orbita-navigation.js'});
const nav = ctx.window.KelwinNav;
assert.equal(nav.directory.length, 8, 'All existing modules remain discoverable');
assert.equal(nav.actions.length, 6, 'All supported creation actions remain discoverable');
const htmlNav = html.match(/<nav id="nav"[^>]*>([\s\S]*?)<\/nav>/)?.[1] || '';
assert.equal((htmlNav.match(/data-tab=/g) || []).length, 4, 'Exactly 4 permanent destinations');
for (const tab of ['today', 'projects', 'events', 'explore'])
  assert(htmlNav.includes('data-tab="' + tab + '"'));
nav.exploreView();
for (const tab of ['tasks','projects','contacts','opportunities','notes','events','automations'])
  assert(view.innerHTML.includes('data-tab="' + tab + '"'), `${tab} missing from the directory`);
const commands = nav.commandSuggestions('criar');
for(const action of ['add-task','add-note','add-project','add-event','add-contact','add-opportunity'])
  assert(commands.includes('data-do="' + action + '"'), `${action} missing from command palette`);
assert(!commands.includes('data-do="complete"'), 'Do not expose destructive commands in palette');
assert(nav.commandSuggestions('áGenda').includes('data-tab="events"'), 'Commands search must ignore accents');
assert(nav.commandSuggestions('').includes('data-tab="today"'), 'Empty search should offer navigation');
assert(html.includes('href="#content"'), 'Skip link must be available');
assert(html.includes('id="create-open"'), 'Create action needs an explicit entry point');
assert(css.includes('safe-area-inset-bottom'), 'Mobile navigation must respect system insets');
assert(css.includes('grid-template-columns:repeat(4,minmax(0,1fr))'), 'Mobile nav must not horizontally overflow');
console.log('ORBITA semantic navigation checks passed.');
