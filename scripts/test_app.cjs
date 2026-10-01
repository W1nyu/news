// Run with node --test scripts/test_app.cjs. No browser or network required.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const {join} = require('node:path');
const vm = require('node:vm');

function app() {
  const elements = new Map();
  const pending = [];
  const element = id => {
    if (!elements.has(id)) elements.set(id, {
      value: '', dataset: {}, style: {}, children: [], selectedOptions: [],
      setAttribute() {}, addEventListener() {},
    });
    return elements.get(id);
  };
  const context = vm.createContext({
    document: {getElementById: element, documentElement: {dataset: {}},
      querySelectorAll: () => [], addEventListener() {}},
    localStorage: {getItem: () => null, setItem() {}},
    fetch: url => new Promise(resolve => pending.push({url, resolve})),
    setTimeout() {}, Intl, Date,
  });
  vm.runInContext(readFileSync(join(__dirname, '../dist/app.js'), 'utf8'), context);
  return {element, pending, run: code => vm.runInContext(code, context)};
}

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
  const {element, run} = app();
  run(`state.missingDate='2026-09-21';
    state.bookmarks.set('https://n.news.naver.com/article/001/123', {
      url:'https://n.news.naver.com/article/001/123',title:'저장한 기사',
      topic:'금융',summary:[],date:'2026-09-20'});`);
  element('categories').onclick({target: {dataset: {category: '저장함'}}});
  assert.match(element('articles').innerHTML, /저장한 기사/);
  assert.doesNotMatch(element('articles').innerHTML, /이 날짜 보고서 만들기/);
  element('categories').onclick({target: {dataset: {category: '전체'}}});
  assert.match(element('articles').innerHTML, /이 날짜 보고서 만들기/);
});

test('headline navigation clears the publisher filter and reaches its card', () => {
  const {element, run} = app();
  run(`state.report={date:'2026-09-22',topics:[{name:'금융',articles:[
    {url:'a',title:'첫 기사',source:'언론사 A'},
    {url:'b',title:'둘째 기사',source:'언론사 B'}]}]};
    state.publisher='언론사 A';`);
  let scrolled = false;
  element('articles').children = [{}, {
    scrollIntoView() {scrolled = true;}, classList: {add() {}, remove() {}},
  }];
  element('headlines').onclick({target: {closest: () => ({dataset: {index: '1'}})}});
  assert.equal(run('state.publisher'), '');
  assert.match(element('articles').innerHTML, /둘째 기사/);
  assert.equal(scrolled, true);
});
