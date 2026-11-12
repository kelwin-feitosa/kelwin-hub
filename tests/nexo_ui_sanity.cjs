/* NEXO read-only render assertions (browser + backend tested separately). */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const root = require('node:path').resolve(__dirname, '..');
const app = fs.readFileSync(root+'/hub/static/app.js','utf8');
const nexo = fs.readFileSync(root+'/hub/static/nexo-context.js','utf8');
const html = fs.readFileSync(root+'/hub/static/index.html','utf8');
const rendered = {innerHTML: '', addEventListener() {}, textContent: ''};
const ctx=vm.createContext({
  window:{addEventListener(){},location:{},history:{}},
  document:{getElementById(id){return id==='content'?rendered:null},querySelector(){return null}},
  setTimeout(){},clearTimeout(){},console, CSS:{escape:s=>s}
});
vm.runInContext(app,ctx,{filename:'app.js'});
vm.runInContext(nexo,ctx,{filename:'nexo-context.js'});
assert(html.includes('/static/nexo-context.js'));
assert(html.includes('/static/nexo-context.css'));
assert(app.includes("if(focusId&&name==='opportunities')"));
assert(app.includes('data-do="opportunity-context"'));
assert(app.includes("case'add-opportunity-note'"));
assert(app.includes('data.notes'));
assert(app.includes('data.events'));
const rec=vm.runInContext(`(function(){window.KelwinNexo.remember('projects','p1','<img src=x onerror=alert(1)>');return window.KelwinNexo.recentMarkup()})()`,ctx);
assert(rec.includes('&lt;img'));
assert(!rec.includes('<img'));
assert(rec.includes('data-nexo-kind="projects"'));
vm.runInContext('window.KelwinNexo.clear()',ctx);
assert(vm.runInContext('window.KelwinNexo.recentMarkup()',ctx)==='');
console.log('NEXO contextual UI semantic checks passed.');