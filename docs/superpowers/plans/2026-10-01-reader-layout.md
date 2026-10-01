# 2단 읽기 · 라이트 기본 · 읽기 편의 기능 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. 이번에는 같은 세션에서 인라인으로 실행한다.

**Goal:** 카드 격자를 제목 목록 + 기사 상세 2단으로 바꾸고, 기본 라이트 테마·안 읽은 기사 중심 탐색·키보드 단축키·글자 크기·제목·링크 복사를 추가한다.

**Architecture:** 빌드 없는 순수 JS(`dist/app.js`) 유지. 렌더는 문자열 템플릿 → `innerHTML`. 상세 마크업을 오른쪽 패널(`#detail`)과 선택 행 아래(`.row-detail`)에 같이 그리고, CSS 미디어 쿼리(1024px)가 하나만 보이게 한다. 상태는 `state` 하나, 브라우저 저장은 localStorage.

**Tech Stack:** HTML/CSS(SEED 토큰, `light-dark()`), vanilla JS, `node --test` + `vm` 하네스, Python 서버(변경 없음).

스펙: `docs/superpowers/specs/2026-10-01-reader-layout-design.md`

---

## 파일 구조

| 파일 | 책임 | 줄끝 |
|---|---|---|
| `scripts/test_app.cjs` | 가짜 DOM 하네스 + 동작 테스트 | LF |
| `dist/app.js` | 상태·필터·렌더·동작·단축키·보기 설정 | CRLF |
| `dist/index.html` | 골격, head 테마/글자 스크립트, popover·dialog·토스트 | CRLF |
| `dist/tokens.css` | `--reading-scale` | LF |
| `dist/app.css` | 2단 레이아웃·목록·상세·개요·탭 숫자·popover·토스트 | LF |
| `AGENTS.md`, `README.md` | UI 목록·저장 항목·검증 명령 | CRLF |

---

### Task 1: 하네스 보강 + 실패하는 테스트

**Files:** Modify `scripts/test_app.cjs`

- [ ] **Step 1: 하네스에 keydown 디스패치·querySelector·window.open·clearTimeout 추가**

```js
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
```

- [ ] **Step 2: 기존 테스트 2·3 갱신 + 새 테스트 6개 추가**

```js
// 테스트 2: 탭 클릭은 closest로 찾는다
element('categories').onclick(pick('[data-category]', {category: '저장함'}));
...
element('categories').onclick(pick('[data-category]', {category: '전체'}));

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
```

- [ ] **Step 3: 실패 확인** — `node --test scripts/test_app.cjs` → 새 테스트 FAIL(`state.selected` 없음, `listeners.keydown` 미정의 등).

### Task 2: `dist/app.js` 재구성

**Files:** Modify `dist/app.js` (CRLF 유지)

유지하는 함수(변경 없음): `esc`, `store`, `toggleBookmark`, `findArticle`, `highlight`, `message`, `dateText`, `json`, `reportArticles`, `weekReport`, `kstDate`, `shiftDate`, `rangeBounds`, `inRange`, `baseArticles`, `renderPublishers`, `searchText`, `keywordsFor`, `loadKeywords`, `renderBanner`, `renderTrend`, `renderDates`, `loadReport`, `loadArchive`, `setCollectButtons`, `poll`(limit 초기화만 `resetView()`로), `startCollect`, 키워드 설정 함수들.

제거: `card`, `relatedList`, 순환 테마 버튼(`THEMES` 순환, `applyTheme`, `$('theme')`), `#articles`의 `h2 a`/`.related-toggle` 처리.

추가 (state에 `selected:''`, `visible:[]`, `keep:new Set()`, `unreadOnly`(`briefing.unread-only.v1`), `limit:PAGE`(80)):

| 함수 | 동작 |
|---|---|
| `saveRead()` / `markRead(url)` / `toggleRead(url)` | 읽음 Set → `briefing.read.v1`(최근 2000) |
| `showHeadlines()` | 검색·저장함·미수집 아님 + 보고서 있음 |
| `headlineArticles()` | 키워드 점수 → 최신순 6건 |
| `headlineButton(a)` | `data-select` + `data-headline="1"` 버튼 |
| `applyFilters(list)` | 언론사 → 기간 → 검색어 |
| `filteredArticles()` | `baseArticles()` + 섹션 + `applyFilters` |
| `visibleArticles()` | 안 읽은 것만(저장함 제외): 읽지 않았거나 `keep`에 있는 것 |
| `unreadCounts()` | 탭별 안 읽은 수(`전체` 포함). 미수집이면 0 |
| `relatedItems(a)` | url 있는 관련 기사 |
| `detail(a, showDate)` | 배지·날짜, 제목 링크(`data-open`), 메타, 버튼(`data-open` 원문 열기 / `data-bookmark` / `data-copy` / `data-toggle-read` / `data-date`), 요약, 관련 보도 |
| `row(a, showDate)` | `<li class="row [read] [selected]">` + `<button class="row-main" data-select>` + 선택 시 `.row-detail` |
| `overview(list)` | 헤드라인 6 + 섹션별 안 읽음/전체(`data-category`) + 단축키 안내(`data-shortcuts`). 검색·저장함은 `n건` |
| `renderTabs()` | 탭 + `<span class="count">n</span>`(0 생략), `aria-keyshortcuts` 0~9 |
| `renderHeadlines()` | 좁은 화면용 가로 줄 |
| `renderList(list, showDate)` | `전체`이고 검색이 아니면 섹션 묶음, 아니면 한 묶음. 묶음 머리 `안 읽음 n/m` + `data-read-all`. `state.visible` = 그린 순서 |
| `render()` | 미수집이 아니면 `renderPublishers` → 탭·헤드라인·토글 상태 → 목록 → `#more` → `#detail`(선택 or 개요) → 갱신 문구·배너. 선택이 목록에 없으면 해제 |
| `resetView()` | `limit=PAGE`, `keep = {selected}` |
| `select(url)` | 선택/해제, 읽음, `keep` 추가, 필요 시 `limit` 확장, 렌더, 상세 맨 위로, 행 `scrollIntoView({block:'nearest'})` |
| `selectHeadline(url)` | 섹션 전체·검색어·언론사 해제, `keep` 비우고 `select` |
| `move(delta)` | `state.visible` 기준 다음/이전, 끝에서 `더 보기` 있으면 확장 |
| `setCategory(name)` / `setUnreadOnly(on)` / `readAll(name)` / `openReport(date)` | 각 동작 후 `resetView` + 렌더 (`readAll`은 `keep`에서 빼고 렌더) |
| `copyText(a)` / `copyArticle(a)` / `toast(text)` | `제목 (언론사)\nURL`, clipboard → execCommand 폴백, 2초 토스트 |
| `onAction(e)` | `#articles`·`#detail`·`#headlines`·`#categories` 공용 클릭 위임 |
| `onAux(e)` | 가운데 클릭 원문/관련 보도 읽음 |
| `shortcutKey(e)` / `onKey(e)` | 영문 키는 `e.code`(한글 입력 상태 대응), 입력 중·dialog 열림·수정키 무시 |
| `applyDisplay()` | `briefing.theme.v2`(기본 light)·`briefing.font.v1`(기본 m) 적용, 메뉴 `aria-pressed` 갱신. 예전 `briefing.theme.v1` 삭제 |

- [ ] **Step 1: 위 규격대로 구현**
- [ ] **Step 2: `node --check dist/app.js` → 오류 없음, `node --test scripts/test_app.cjs` → 10 pass**

### Task 3: `dist/index.html`

- [ ] head 인라인 스크립트: `briefing.theme.v2`가 `system`이 아니면 `data-theme`(dark 외는 light), `briefing.font.v1`이 s/l이면 `data-font`.
- [ ] 앱바: `#theme` 제거 → `#display-button`(`popovertarget="display"`, 아이콘 + `보기`).
- [ ] `<div id="display" popover>`: 테마 라이트/다크/시스템(`data-theme-choice`), 글자 크기 작게/보통/크게(`data-font-choice`).
- [ ] `.filters` 끝에 `<button id="unread-only" class="toggle" aria-pressed="false">안 읽은 것만</button>`.
- [ ] `#articles.cards` → `.reader` > `.list-pane`(`#articles`, `#more`) + `<aside id="detail" class="detail-pane">`.
- [ ] `<dialog id="shortcut-dialog">`(단축키 표, `#shortcut-close`), `<div id="toast" role="status" hidden>`.

### Task 4: CSS

- [ ] `tokens.css`: `:root{--reading-scale:1}`, `[data-font="s"]` .9, `[data-font="l"]` 1.15.
- [ ] `app.css`: `--appbar-h`(56/64) · `--tabs-h`(52) · `--sticky-top`. 탭은 모든 폭에서 sticky·가로 스크롤 + `.count`. 헤드라인은 가로 스크롤 칩. 카드·북마크·관련 토글·테마 버튼 규칙 삭제 → `.group`, `.row`, `.row-main`, `.row-title`(2줄), `.dot`, `.row-detail`, `.detail-body`, `.detail-actions`, `.summary`, `.overview`, `.toggle`, `#display`, `.segmented`, `.shortcuts`, `kbd`, `#toast`. `@media (min-width:1024px)`: `.reader` 5fr/7fr 그리드, `.detail-pane` sticky + 자체 스크롤, `.row-detail`·`#headlines` 숨김, 제목 줄 축소. 글자 크기는 `calc(토큰 * var(--reading-scale))`.

### Task 5: 검증 · 커밋

- [ ] `node --check dist/app.js`, `node --test scripts/test_app.cjs`, `python -m unittest discover -s scripts -p "test_*.py"`.
- [ ] 브라우저(실행 중인 8765 서버, 정적 파일이라 재시작 불필요): 1440/1024/800px × 라이트/다크, 글자 크기, `j k Enter s c m u / Esc ? 0-9`, 저장함·검색·7일·미수집 날짜, 가로 스크롤 없음.
- [ ] CRLF 복원(`unix2dos dist/app.js dist/index.html`) 후 커밋: `feat: two-pane reader with unread focus, shortcuts, font size, copy link and light default`.

### Task 6: 문서

- [ ] `AGENTS.md` UI 목록·localStorage 항목·개발 검증에 `node --test scripts/test_app.cjs`.
- [ ] `README.md` 화면 절 갱신.
- [ ] 커밋 `docs: reader layout, shortcuts and display settings` → `git push origin main`.
