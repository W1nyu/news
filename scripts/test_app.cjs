// Run with node --test scripts/test_app.cjs. No browser or network required.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const {join} = require('node:path');
const vm = require('node:vm');

function app() {
  const elements = new Map();
  const pending = [];
  const listeners = {};
  const opened = [];
  const element = id => {
    if (!elements.has(id)) elements.set(id, {
      id, value: '', dataset: {}, style: {}, children: [], selectedOptions: [],
      setAttribute() {}, addEventListener() {}, querySelector: () => null, focus() {},
    });
    return elements.get(id);
  };
  const context = vm.createContext({
    document: {getElementById: element, documentElement: {dataset: {}},
      querySelector: () => null, querySelectorAll: () => [],
      addEventListener(type, fn) { listeners[type] = fn; }},
    localStorage: {getItem: () => null, setItem() {}},
    window: {open: (...args) => opened.push(args)},
    fetch: url => new Promise(resolve => pending.push({url, resolve})),
    setTimeout() {}, clearTimeout() {}, Intl, Date,
  });
  vm.runInContext(readFileSync(join(__dirname, '../dist/app.js'), 'utf8'), context);
  const key = (k, extra = {}) => {
    const e = {key: k, code: /^[a-z]$/.test(k) ? `Key${k.toUpperCase()}` : '', target: {tagName: 'BODY'},
      preventDefault() { e.prevented = true; }, ...extra};
    listeners.keydown(e);
    return e;
  };
  const pick = (selector, dataset) => ({target: {closest: s => s === selector ? {dataset} : null}});
  return {element, pending, opened, key, pick, run: code => vm.runInContext(code, context)};
}

const REPORT = `state.report={date:'2026-09-22',topics:[
  {name:'금융',articles:[{url:'a',title:'알파 기사',source:'언론사 A'},{url:'b',title:'베타 기사',source:'언론사 B'}]},
  {name:'증권',articles:[{url:'c',title:'감마 기사',source:'언론사 A'}]}]};`;

test('a late report response cannot replace a missing date selection', async () => {
  const {element, pending, run} = app();
  element('date').value = '2026-09-21';
  element('date').selectedOptions = [{dataset: {missing: '1'}}];
  element('date').onchange();
  pending.find(p => p.url === 'data/latest.json').resolve({ok: true,
    json: async () => ({schema_version: 4, date: '2026-09-22', topics: []})});
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(run('state.report'), null);
  assert.equal(run('state.missingDate'), '2026-09-21');
  assert.match(element('articles').innerHTML, /2026-09-21 보고서가 없습니다/);
});

test('saved articles remain accessible from a missing date', () => {
  const {element, run, pick} = app();
  run(`state.missingDate='2026-09-21';
    state.bookmarks.set('https://n.news.naver.com/article/001/123', {
      url:'https://n.news.naver.com/article/001/123',title:'저장한 기사',
      topic:'금융',summary:[],date:'2026-09-20'});`);
  element('categories').onclick(pick('[data-category]', {category: '저장함'}));
  assert.match(element('articles').innerHTML, /저장한 기사/);
  assert.doesNotMatch(element('articles').innerHTML, /이 날짜 보고서 만들기/);
  element('categories').onclick(pick('[data-category]', {category: '전체'}));
  assert.match(element('articles').innerHTML, /이 날짜 보고서 만들기/);
});

test('headline selection clears filters and keeps the article visible', () => {
  const {element, run, pick} = app();
  run(REPORT + `state.publisher='언론사 A';state.unreadOnly=true;state.read.add('b');render();`);
  assert.doesNotMatch(element('articles').innerHTML, /베타 기사/);
  element('headlines').onclick(pick('[data-select]', {select: 'b', headline: '1'}));
  assert.equal(run('state.publisher'), '');
  assert.equal(run('state.selected'), 'b');
  assert.match(element('articles').innerHTML, /베타 기사/);
  assert.match(element('detail').innerHTML, /베타 기사/);
});

test('section tabs show unread counts for the current report', () => {
  const {element, run} = app();
  run(REPORT + `state.read.add('c');render();`);
  const tabs = element('categories').innerHTML;
  assert.match(tabs, /data-category="전체"[^>]*>전체<span class="count">2<\/span>/);
  assert.match(tabs, /data-category="금융"[^>]*>금융<span class="count">2<\/span>/);
  assert.doesNotMatch(tabs, /증권<span class="count">/);
});

test('unread-only keeps articles read in this view until the view changes', () => {
  const {element, run, key, pick} = app();
  run(REPORT + `state.read.add('c');render();`);
  element('unread-only').onclick();
  assert.equal(run('state.unreadOnly'), true);
  assert.doesNotMatch(element('articles').innerHTML, /감마 기사/);
  key('j'); key('j');
  assert.equal(run('state.selected'), 'b');
  assert.match(element('articles').innerHTML, /알파 기사/);
  element('categories').onclick(pick('[data-category]', {category: '금융'}));
  assert.doesNotMatch(element('articles').innerHTML, /알파 기사/);
  assert.match(element('articles').innerHTML, /베타 기사/);
});

test('keyboard moves the selection, toggles read and opens the original', () => {
  const {element, run, key, opened} = app();
  run(REPORT + 'render();');
  key('j');
  assert.equal(run('state.selected'), 'a');
  assert.equal(run('state.read.has("a")'), true);
  assert.match(element('detail').innerHTML, /알파 기사/);
  key('ArrowDown'); key('j');
  assert.equal(run('state.selected'), 'c');
  key('j');
  assert.equal(run('state.selected'), 'c');
  key('k');
  assert.equal(run('state.selected'), 'b');
  key('m');
  assert.equal(run('state.read.has("b")'), false);
  assert.match(element('detail').innerHTML, /data-toggle-read="b">읽음으로</);
  key('Enter');
  assert.deepEqual(opened.map(args => args[0]), ['b']);
  assert.equal(run('state.read.has("b")'), true);
  key('Escape');
  assert.equal(run('state.selected'), '');
});

test('mark all read clears one section group', () => {
  const {element, run, pick} = app();
  run(REPORT + 'state.unreadOnly=true;render();');
  assert.match(element('articles').innerHTML, /data-read-all="금융"/);
  element('articles').onclick(pick('[data-read-all]', {readAll: '금융'}));
  assert.equal(run('state.read.has("a") && state.read.has("b") && !state.read.has("c")'), true);
  assert.doesNotMatch(element('articles').innerHTML, /알파 기사|베타 기사/);
  assert.match(element('articles').innerHTML, /감마 기사/);
});

test('shortcuts are ignored while typing and number keys switch sections', () => {
  const {run, key} = app();
  run(REPORT + 'render();');
  const typed = key('j', {target: {tagName: 'INPUT', id: 'search'}});
  assert.equal(run('state.selected'), '');
  assert.equal(typed.prevented, undefined);
  key('2');
  assert.equal(run('state.category'), '증권');
  key('9');
  assert.equal(run('state.category'), '저장함');
  key('0');
  assert.equal(run('state.category'), '전체');
});

test('light is the default theme and copy text is title, publisher and link', () => {
  const {run} = app();
  assert.equal(run('document.documentElement.dataset.theme'), 'light');
  assert.equal(run('document.documentElement.dataset.font'), undefined);
  assert.equal(run(`copyText({title:'제목',source:'언론사',url:'https://n.news.naver.com/x'})`),
    '제목 (언론사)\nhttps://n.news.naver.com/x');
});
