# 아침 경제 2차 개선 설계 — 요약 품질 · 유사 기사 묶기 · 검색 필터

작성일: 2026-09-14 (1차: `2026-09-14-collection-ux-phase1-design.md`)

## 목표

1. 요약 문장을 제목 연관 점수로 고른다(모델 API 없음).
2. 같은 사건을 다룬 기사를 수집 단계에서 묶어 대표 1건 + 관련 보도로 표시한다.
3. 요약 문장 안의 키워드도 강조한다.
4. 보관함 검색에 기간(발행일)·언론사 필터를 더한다.

범위 밖: 주간 보기, 기사 수 추이, 요약 점수의 순위 반영.

## 1. 요약 문장 선별 (`scripts/article_details.py`)

- `inspect_article(page, source_id, title_hint=None, keywords=())` — 두 인자를 추가한다. 기존 호출(인자 2개)은 그대로 동작한다.
- 적격 문장 조건은 기존과 같다(25~220자, `?`로 끝나지 않음, 홍보·저작권·기자 서명 제외, `[앵커]` 접두 제거). 적격 문장 중 **앞 12개**만 후보로 본다.
- `bigrams(text)`: 공백·기호를 제거한 문자열의 글자 2-gram 집합. `dice(a, b)`: `2|a∩b| / (|a|+|b|)`, 둘 다 비면 0.
- 점수 `score(sentence, index)` = `dice(bigrams(sentence), bigrams(title))*3 + (키워드가 문장에 포함된 개수, 대소문자 무시)*1 + (숫자·%·원·억·조 포함 시 0.5) − index*0.05`. `title_hint`가 없으면 og:title, 그것도 없으면 Dice 항은 0.
- 선택: 후보 첫 문장(리드)은 항상 첫 번째. 두 번째는 나머지 후보를 점수 내림차순으로 보며 `dice(문장, 리드) < 0.6`이고 누적 70단어 이내인 첫 문장. 없으면 리드 1문장만.
- 반환 `summary_method`는 `'제목 연관 발췌'`.

## 2. 유사 기사 묶기 (`scripts/naver_pipeline.py`)

### 판정
- `title_key(title)`: `[...]`·`(...)`·`<...>` 블록과 기호를 제거하고 공백을 하나로 정리한 문자열. `title_bigrams(title)`는 그 2-gram 집합.
- `DIRECTION_PAIRS = [('상승','하락'),('증가','감소'),('매수','매도'),('흑자','적자'),('인상','인하'),('확대','축소'),('급등','급락'),('강세','약세')]`
- `similar(a, b)`(제목 문자열 두 개) → 모두 만족하면 참:
  1. `dice(title_bigrams(a), title_bigrams(b)) >= 0.45`
  2. 각 제목의 숫자 토큰 집합(`re.findall(r'\d+(?:[.,]\d+)?', ...)`)이 같거나, 한쪽이 비어 있다.
  3. `DIRECTION_PAIRS`의 어느 쌍에서도 한 제목에는 왼쪽 단어만, 다른 제목에는 오른쪽 단어만 있는 경우가 없다.

### 수집 흐름 변경 (`collect()`)
- `selected_all`: 이번 실행에서 지금까지 선택된 대표 기사 목록(전 섹션). `RELATED_LIMIT = 4`, `EXTRA_FETCH_LIMIT = 8`.
- 후보 순회(기존 루프) 안에서, 검증(무료·발행 시각·72시간/대상 날짜)을 통과한 기사에 대해:
  - `selected_all` 중 `similar(제목, 대표 제목)`이 참인 첫 대표가 있으면 → `related`가 4건 미만이면 그 대표의 `related`에 `{url, title, source, published_at, section}`을 추가하고 `excluded['grouped'] += 1`, 이미 4건이면 버리고 `excluded['grouped_overflow'] += 1`. 어느 쪽이든 `used`·`titles`에 등록하고 한도(`limit`)에는 산입하지 않는다(유사 기사는 새 카드가 되지 않는다).
  - 유사한 대표가 없으면 기존처럼 `selected`에 추가하고 `selected_all`에도 추가한다(`related: []` 포함).
- 한도를 채워 `break`한 뒤: 남은 후보 중 `used`에 없고 제목이 `selected_all`의 어느 대표와 `similar`한 것만 골라, 섹션당 최대 8건까지 검증 후 위와 같이 `related`에 붙인다. 검증 실패는 기존 사유로 집계한다.
- 중복 제목(`fingerprint`) 검사는 유사 판정보다 먼저 적용된다(완전 동일 제목은 지금처럼 `duplicate`).
- 캐시는 기존 30분 캐시를 그대로 쓴다(관련 기사도 캐시 대상).
- `inspect_article` 호출에 `title_hint=option['title']`, `keywords=keywords`를 넘긴다.
- `stats`에 `'related': 전체 관련 기사 수` 추가. `stats['selected']`는 대표 기사 수. `schema_version` 4 유지.
- 관련 기사도 동일한 검증을 통과해야 한다. 미확인·유료·기간 밖 기사는 관련으로도 넣지 않는다.

### `save_report`
- `search.json` 행은 대표 기사 단위이며 `related` 배열을 그대로 포함한다(별도 행으로 펼치지 않음).

## 3. 화면

### 툴바 (`dist/index.html`, `dist/minimal.css`)
- 구성: `[날짜 ▾] [검색어] [기간 ▾] [언론사 ▾]`, 600px 이하 세로 배치.
- `#range` 옵션: `all` "전체 기간"(기본), `7` "최근 7일", `30` "최근 30일", `custom` "직접 입력". `custom`이면 `#range-custom`(`<input type=date id=from>` ~ `<input type=date id=to>`)이 툴바 아래에 표시된다.
- `#range`는 검색어가 비어 있으면 `disabled`. 검색어가 있으면 활성.
- `#publisher` 옵션: "전체 언론사"(값 `''`) + 현재 화면 후보 기사(카테고리·기간·검색어 적용 **전**, 저장함이면 북마크 전체, 검색 중이면 검색 색인 전체, 아니면 현재 보고서)의 `source`를 건수 내림차순으로 `언론사명 (n)`. 재생성 시 기존 선택값이 목록에 있으면 유지, 없으면 `''`.

### 필터 (`dist/app.js`)
- `state`에 `range:'all'`, `from:''`, `to:''`, `publisher:''` 추가.
- `render()`의 필터 순서: 카테고리 → 언론사(`a.source === state.publisher`) → 기간 → 검색어.
- 기간: 검색어가 있을 때만 적용. `kstDate(published_at)` = `Intl.DateTimeFormat('sv-SE', {timeZone:'Asia/Seoul'})`로 얻은 `YYYY-MM-DD`. `7`/`30`은 `state.today` 기준 `today - (n-1)`일부터 오늘까지. `custom`은 `from`~`to`(비어 있는 경계는 무시, `from > to`면 교환).
- 검색어 매칭 문자열에 `related` 제목들을 포함한다.
- 필터 변경 시 `state.limit = 18`.

### 카드 (`card()`)
- 제목: 기존 `highlight(a.title, a.keyword_matches)`.
- 요약: `highlight(문장, keywordsFor(a))`. `keywordsFor(a)`는 저장함 카드면 북마크 객체의 `keywords`, 그 외에는 `state.keywords`. `state.keywords`는 페이지 로드 시 기존 `GET /api/keywords`를 한 번 읽어 `rules[].keyword` 목록으로 채운다(설정 저장 후에도 갱신).
- `related`가 1건 이상이면 메타 아래 `<button class="related-toggle" aria-expanded="false">관련 보도 n건 ▸</button>`과 숨겨진 `<ul class="related">`. 항목: `언론사 · <a>제목</a> · MM-DD HH:mm`. 토글은 `$('articles')` 위임 클릭으로 처리, 기본 접힘, 상태 저장 안 함.
- 관련 링크 클릭·가운데 클릭도 `markRead(url)`; 읽은 관련 링크는 `.read` 클래스로 연하게(카드 전체는 변하지 않음).
- 북마크 객체에 `related`, `keywords` 추가.

## 4. 오류 처리

- `title_hint`·키워드가 없어도 점수는 순서 항만으로 동작하며 리드 문장은 항상 포함되므로 요약이 비지 않는다.
- 유사 판정용 추가 접근은 섹션당 8건에서 멈춘다. 실패는 `fetch_error`.
- 기간 직접 입력: 시작 > 종료면 교환. 빈 값은 무시.
- `related`가 없는 1차 보고서는 그대로 표시된다.
- `/api/keywords` 로드 실패 시 `state.keywords = []`(요약 강조만 꺼진다).

## 5. 테스트

- `scripts/test_article_details.py`: (a) 제목과 연관된 문장이 리드 뒤에 두 번째로 선택된다, (b) 리드와 Dice ≥ 0.6인 문장은 건너뛴다, (c) `title_hint`·키워드 없이도 2문장을 반환하며 기존 결과와 같다, (d) `summary_method`가 `'제목 연관 발췌'`.
- `scripts/test_naver_pipeline.py`: `similar()` — 조사만 다른 제목 참, 숫자 다른 제목 거짓, 상승/하락 거짓, 무관 제목 거짓, `[단독]` 접두 무시. `collect()` 모킹: 유사 제목 후보가 대표의 `related`에 붙고 `selected` 수는 한도와 같다, 카드당 4건에서 멈춘다, 한도 이후 추가 접근이 8건에서 멈춘다(`fetch` 호출 수로 확인).
- 기존 테스트 전부 통과, `node --check dist/app.js`.
- 수동 확인 1회: 실제 수집 → 관련 보도 묶임, 기간·언론사 필터, 요약 강조, 모바일 폭 툴바.

## 6. 문서

- `README.md`: 요약 방식(제목 연관 발췌: 리드 + 제목·키워드·수치 연관 문장), 관련 보도 묶기 기준(제목 2-gram 유사도 0.45, 숫자·방향어 보정, 카드당 4건, 관련 기사도 검증), 기간(발행일 기준)·언론사 필터.
- `AGENTS.md`: 고정 요구사항에 유사 기사 판정 규칙과 "관련 기사도 무료·발행일 검증 필수" 추가. UI 허용 목록에 기간·언론사 필터, 관련 보도 토글 추가. 요약은 여전히 원문 문장 발췌임을 유지.
