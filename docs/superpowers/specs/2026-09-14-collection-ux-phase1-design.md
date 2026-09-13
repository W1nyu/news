# 아침 경제 1차 개선 설계 — 수집 경로 · PDF 제거 · 읽기 경험

작성일: 2026-09-14

## 목표

1. PC가 꺼져 있어 07:30 예약을 놓쳐도 그날 보고서가 만들어지도록 한다(로그인 트리거 + 수동 경로).
2. PDF 보고서 기능을 완전히 제거한다.
3. 읽기 경험을 개선한다: 헤드라인 리본, 읽음 표시·북마크, 키워드 강조.

2차 이후로 미룬 항목: 수집 품질(요약 선별, 유사 기사 묶기), 보관함/검색 강화(기간 검색, 언론사 필터, 주간 보기).

## 1. 수집 실행 경로

### 1.1 파이프라인 (`scripts/naver_pipeline.py`, `scripts/collector.py`)

- `collect(target_date=None, progress=None)`
  - `target_date`가 없으면 현재 동작 유지: 발행 72시간 이내 기사를 오늘(KST) 날짜로 저장.
  - `target_date`(`datetime.date`)가 있으면 발행 시각(KST)의 날짜가 `target_date`와 같은 기사만 선택하고 `payload['date']`를 그 날짜로 둔다. 섹션별 한도·최소·키워드 정렬은 동일.
  - `progress`는 `progress(done, total, section_name)` 형태의 콜백. 시작 시 `(0, total, '')`로 1회, 이후 섹션 하나가 끝날 때마다 호출한다.
- `collectable_dates(now)`: `[오늘, 어제, 그제]` ISO 문자열 목록. 서버와 CLI가 공유한다.
- `collector.py --date YYYY-MM-DD`
  - 형식 오류이거나 `collectable_dates()`에 없으면 stderr에 메시지를 쓰고 종료 코드 3.
  - 그 외 종료 코드는 기존과 같다: 0 성공, 1 검증 통과 기사 없음, 2 다른 수집 실행 중.
- 진행률 파일 `data/progress.json`
  - 내용: `{"done":3,"total":8,"section":"산업/재계","date":"2026-09-14","started_at":"<ISO>"}`
  - 수집 시작 시 `done:0`으로 생성, 섹션마다 갱신(`atomic_json`), 성공·실패·예외 종료 시 삭제.
  - 쓰기·삭제 실패는 수집을 중단시키지 않는다.
- `save_report(payload)`
  - `build_pdf` 호출과 `pdf_url` 필드를 제거한다.
  - `data/<date>.json`, `dist/data/<date>.json`을 기록한 뒤, `data/????-??-??.json` 중 schema 4인 **가장 최신 날짜** 보고서를 `latest.json`으로 복사한다(양쪽 폴더). 과거 날짜 재수집이 최신 보고서를 덮어쓰지 않는다.
  - `history.json`, `search.json`, `run-status.json` 생성은 유지. `run-status.json`에 `date`는 수집 대상 날짜를 넣는다.
- `schema_version`은 4를 유지한다(필드 제거만 있고 UI가 `pdf_url` 없이도 동작).

### 1.2 PDF 제거

삭제:
- `scripts/report_pdf.py`
- `dist/reports/` 전체, `output/` 전체, `tmp/pdfs/` 전체
- 루트 `reference*.png`, `report-qa-*.png`, `final-report-*.png`, `final-report-contact.png`

수정:
- `scripts/verify_report.py`: `pypdf`, `PIL` 의존과 PDF·이미지 검사 제거. JSON 보고서 검증(URL 중복, 섹션 한도, 무료·발행일·요약 검사)만 남긴다.
- `requirements.txt`: `reportlab` 제거(`beautifulsoup4`만 남음).
- `.gitignore`: `output/`, `dist/reports/`, `*-qa-*.png`, `reference*.png`, `final-report-*.png` 줄 제거.
- `dist/index.html`: `#pdf` 링크 제거. `dist/app.js`: `pdf_url` 관련 두 줄 제거.
- 기존 보고서 JSON의 `pdf_url` 키는 그대로 두어도 무해하며, 재수집 시 사라진다.

### 1.3 Windows 작업과 바로가기

`scripts/install_daily_task.ps1` (재작성, `Register-ScheduledTask` 사용):
- 인자가 다른 두 실행이 필요하므로 작업을 두 개 등록한다(둘 다 기존 것을 덮어쓴다):
  - `Daily Economy Briefing`: 매일 `-Time`(기본 07:30) → `powershell -NoProfile -ExecutionPolicy Bypass -File run_daily_briefing.ps1`
  - `Daily Economy Briefing (Logon)`: 현재 사용자 로그인 시 1분 지연 → 같은 스크립트에 `-IfMissing`
  - `-Uninstall` 스위치로 두 작업을 함께 제거한다.
- 설정: `StartWhenAvailable`, `AllowStartIfOnBatteries`, `DontStopIfGoingOnBatteries`, 실행 시간 제한 30분, 이미 실행 중이면 새 인스턴스 무시.
- 바탕화면 바로가기 `아침 경제 수집.lnk` 생성: 대상 `powershell.exe -NoProfile -ExecutionPolicy Bypass -File "<scripts>\run_daily_briefing.ps1" -Open`, 작업 폴더는 프로젝트 루트. 바로가기가 이미 있으면 덮어쓴다.

`scripts/run_daily_briefing.ps1`:
- `-IfMissing`: `data/<오늘 KST>.json`이 있으면 아무것도 하지 않고 종료 코드 0.
- 그 외 동작은 기존과 같다(수집 → `-Open`이면 서버 확인·시작 → 브라우저).
- 수집 종료 코드가 2(다른 수집 실행 중)이면 `-Open`은 계속 진행한다(화면에서 진행 상황을 보게 함).

## 2. 서버 API (`scripts/server.py`)

### `GET /api/status`

```json
{
  "running": true, "ok": null, "message": "뉴스를 수집하고 있습니다.",
  "progress": {"done": 3, "total": 8, "section": "산업/재계", "date": "2026-09-14"},
  "today": "2026-09-14", "latest_date": "2026-09-13",
  "collectable_dates": ["2026-09-14", "2026-09-13", "2026-09-12"]
}
```
- `progress`: 수집 중이고 `data/progress.json`을 읽을 수 있으면 그 내용, 아니면 `null`.
- `today`: 서버 KST 기준 오늘. `latest_date`: `data/latest.json`의 `date`, 없으면 `null`.
- `collectable_dates`: `collectable_dates(now)`.

### `POST /api/collect`

- 기존 same-origin 검사(Host, Origin, `X-Briefing-Request: collect`) 유지.
- 본문이 없거나 비어 있으면 오늘 수집.
- 본문이 JSON `{"date": "YYYY-MM-DD"}`이면 `collector.py --date <date>` 실행. 형식이 다르거나 `collectable_dates()`에 없으면 400 `{"error": "..."}`.
- 잠금 획득 실패 시 409 + 현재 상태(기존과 같음).
- 완료 메시지는 종료 코드별로 한 줄: 0 "수집 완료", 1 "검증을 통과한 기사가 없어 이전 보고서를 유지합니다.", 2 "다른 수집이 실행 중입니다.", 3 "수집할 수 없는 날짜입니다.", 그 외 "수집 실행 오류. 이전 보고서를 유지합니다."
- `STATUS`에 `date`(마지막 수집 대상 날짜)를 포함해 UI가 완료 후 어느 날짜를 열지 알 수 있게 한다.

`POST /api/keywords`는 변경 없음. 정적 서빙은 `dist/reports/`가 사라지는 것 외 변경 없음.

## 3. 화면 (`dist/index.html`, `dist/app.js`, `dist/minimal.css`)

### 헤더
- `보고서 PDF ↗` 제거. `키워드 설정`, `지금 수집` 유지.

### 오늘 보고서 없음 배너 (`#missing-today`, 제목 행 아래)
- 표시 조건: `latest_date < today`이고 `running`이 아님.
- 내용: "오늘(09-14) 보고서가 아직 없습니다. 최근 보고서는 09-13입니다." + `지금 수집` 버튼(헤더 버튼과 동일 동작).
- 수집 시작 후에는 숨기고 진행 표시로 대체한다.

### 진행 표시
- `#status`에 "수집 중 · 3/8 산업/재계" 형식과 얇은 진행 막대(`#progress-bar`, width = done/total).
- 폴링 간격 2초 유지. 완료 시 "새 보고서가 준비됐습니다." 후 해당 날짜 보고서를 불러온다.

### 날짜 선택
- 옵션: `최신 보고서` + 보관함 날짜 + (`collectable_dates` 중 보관함에 없는 날짜)를 `YYYY-MM-DD (미수집)`으로 추가, 날짜 내림차순 정렬.
- 미수집 날짜 선택 시 카드 영역에 "이 날짜 보고서가 없습니다." + `이 날짜 보고서 만들기` 버튼. 클릭하면 `POST /api/collect` `{date}`.
- 완료 후 `STATUS.date`의 보고서를 불러와 표시하고 날짜 목록을 갱신한다.

### 헤드라인 리본 (`#headlines`, 섹션 탭 위)
- 검색어가 없고 보고서가 있을 때만 표시.
- 현재 보고서의 모든 기사를 `keyword_score` 내림차순 → `published_at` 내림차순으로 정렬해 6건. 모든 점수가 0이면 결과적으로 최신순 6건이 된다(별도 분기 없음).
- 항목: 섹션명 + 제목 한 줄(줄임표). 클릭 시 섹션을 `전체`로, `limit`을 해당 인덱스+1 이상으로 늘린 뒤 렌더하고 카드로 `scrollIntoView`, 1.5초 강조 클래스.

### 읽음 표시 + 북마크 (localStorage)
- 키 `briefing.read.v1`: URL 배열(최대 2,000개, 초과 시 오래된 것부터 제거). 제목 링크의 `click`·`auxclick` 시 추가. 읽은 카드는 `.read` 클래스로 제목·요약 색을 연하게.
- 키 `briefing.bookmarks.v1`: `{url: {url,title,source,topic,date,published_at,summary,keyword_matches,saved_at}}`. 카드 우상단 `☆/★` 토글 버튼(`aria-pressed`).
- 섹션 탭 끝에 `저장함 (n)` 탭. 선택 시 북마크 전체를 `date` 내림차순, 같은 날짜는 `published_at` 내림차순으로 표시. 검색어 필터도 적용. 리본은 숨김.
- localStorage 읽기·쓰기는 모두 try/catch. 실패하면 빈 집합으로 동작하고 저장은 무시한다.

### 키워드 강조
- 제목을 HTML 이스케이프한 뒤 `keyword_matches`의 각 키워드를 대소문자 무시로 `<mark>`로 감싼다. 긴 키워드부터 처리해 중첩을 피한다. 카드에 별도 키워드 칩은 두지 않는다.

### 코드 구조
- `state`에 `today`, `latestDate`, `collectable`, `bookmarks`(Map), `read`(Set) 추가.
- `articleCard(article)` 함수를 분리해 일반 카드·저장함이 공유한다. 리본은 `headlineItem(article, index)`.
- `render()`는 리본 → 탭 → 카드 → 더 보기 순으로 갱신. 미수집 날짜 화면은 `render()` 안에서 `state.missingDate`가 있으면 카드 대신 안내를 그린다.

## 4. 오류 처리

- 과거 날짜 수집에서 해당 날짜 기사가 0건이면 코드 1로 종료하고 기존 파일을 보존한다.
- `progress.json` 쓰기·삭제 실패는 무시한다. 서버는 파싱 실패 시 `progress: null`.
- 로그인 트리거 실행 시 네트워크가 없으면 모든 섹션이 `fetch_error`로 실패해 코드 1로 끝난다. 자체 재시도는 두지 않는다. 다음 로그인 또는 수동 실행 때 다시 시도된다.
- 브라우저 저장소 예외는 기능만 비활성화하고 화면 오류를 내지 않는다.

## 5. 테스트

- `scripts/test_naver_pipeline.py`에 추가:
  - `collectable_dates()`가 오늘·어제·그제를 반환.
  - 날짜 필터: KST 자정 직전·직후 기사가 각각 올바른 날짜로 분류.
  - `save_report()`가 과거 날짜 보고서를 저장해도 `latest.json`이 최신 날짜를 유지(임시 폴더 사용).
  - 진행 콜백이 시작 1회 + 섹션 수만큼 호출(네트워크는 `fetch` 모킹).
- `scripts/test_server.py` 신규: 핸들러의 날짜 검증 함수 단위 테스트(허용·거부·형식 오류)와 `/api/status` 응답 필드 구성 함수 테스트. 실제 소켓은 열지 않는다.
- 기존 테스트 전부 통과, `node --check dist/app.js`.
- 수동 확인 1회: 실제 수집 → 화면에서 배너·진행률·리본·북마크·읽음·미수집 날짜 재수집 흐름. `Get-ScheduledTask`로 작업 2개와 `StartWhenAvailable` 확인. 바탕화면 바로가기 더블클릭 확인.

## 6. 문서

- `README.md`: PDF 문구 삭제. 설치 명령(`install_daily_task.ps1` 재실행) 안내, 로그인 시 자동 보완 설명, 바탕화면 바로가기, `--date` 옵션과 최근 3일 제한, 읽음·북마크는 브라우저별 저장임을 명시.
- `AGENTS.md`: "PDF는 같은 실행에서 자동 작성" 삭제. UI 허용 목록을 "날짜, 검색, 섹션, 뉴스 요약, 수집 버튼, 진행률, 오늘 보고서 없음 배너, 헤드라인 리본, 읽음·북마크, 키워드 설정"으로 갱신. `--date` 옵션과 종료 코드 3 추가. `latest.json`이 최신 날짜 기준임을 명시.
