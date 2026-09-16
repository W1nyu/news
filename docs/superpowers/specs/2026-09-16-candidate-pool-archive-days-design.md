# 6차 설계: 수집 후보 풀 확대 · 날짜별 목록 · 검색 색인 보관 기간

날짜: 2026-09-16

## 배경

- `config/sections.json`의 `candidate_limit: 60`은 실제로 쓰이지 않았다. 네이버 섹션 HTML 첫 페이지가 36건만 주고 다음 페이지를 읽지 않기 때문이다. `--date` 재수집도 첫 페이지에 남은 기사만 대상이라 결과가 적었다.
- `dist/data/search.json`은 모든 날짜 보고서를 합친 파일이고 페이지를 열 때마다 통째로 받는다(하루 72건 → 연 약 26MB).

## 실측(2026-09-16)

`https://news.naver.com/section/template/SECTION_ARTICLE_LIST_FOR_LATEST?sid=101&sid2=<섹션>&cluid=&pageNo=<n>&date=<YYYYMMDD|빈값>&next=<커서|빈값>`

- 응답: `{"renderedComponent":{"SECTION_ARTICLE_LIST_FOR_LATEST":"<html 조각>"}}`. 조각에 `.section_latest_article` 래퍼가 있어 기존 `candidates()`로 파싱된다.
- 다음 페이지 커서: 조각·HTML 페이지 모두 `data-cursor-name="next" data-cursor="<숫자>"`. `next` 커서를 넘기면 다음 36건(중복 0). `pageNo`만 올리면 같은 페이지가 반복된다.
- `date=20260915`를 주면 그 날짜 목록이 온다(오늘 목록과 중복 0, 2페이지도 동작).

## 결정

1. **후보 목록 수집** (`naver_pipeline.section_candidates`)
   - 기본 실행: 섹션 HTML 첫 페이지(기존 경로) → `next` 커서로 템플릿 페이지를 `candidate_limit`까지 추가로 읽는다.
   - `--date`: 템플릿 엔드포인트의 `date=` 목록을 첫 페이지부터 사용한다.
   - 다음 페이지 실패(네트워크·형태 변경)는 섹션 실패가 아니라 그때까지 모은 후보로 진행한다. 첫 페이지 실패는 기존처럼 섹션 `error`.
   - 페이지 간 URL 중복은 한 번만 남기고, 새 후보가 0이면 중단한다. 결과는 `candidate_limit`으로 자른다.
2. **보관 기간** (`archive_days`, 기본 90)
   - `save_report`가 history/search/latest 색인을 만들 때 가장 최신 보고서 날짜 기준 `archive_days` 안의 파일만 읽는다. 날짜별 JSON 파일은 삭제하지 않는다.
   - `/api/status`에 `archive_days`를 넣어 검색 입력 placeholder에 "최근 N일 뉴스 검색"으로 표시한다. 다른 UI 변화 없음.
3. 같은 날 재수집 병합은 이번 범위에서 제외.

## 검증

단위 테스트(커서 파싱·페이지 추적·실패 시 1페이지 유지·색인 보관 기간·상태 응답) + 실제 수집(오늘·어제) 각 1회 + 브라우저 확인.
