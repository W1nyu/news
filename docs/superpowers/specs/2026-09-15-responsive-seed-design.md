# 반응형 · SEED 토큰 리디자인 (2026-09-15)

## 목표

`dist/` 화면을 모바일 퍼스트 반응형으로 다시 만들고, 시각 체계를 당근 SEED Design v2.7(`seed-design-dev/packages/css/base.css`) 토큰 위에 올린다. 기능(AGENTS.md의 UI 목록)은 추가·삭제하지 않는다.

## 결정

- **브랜드 색은 딥그린 유지**: SEED carrot 자리를 `#1b5344` 계열로 대체. 라이트 `bg-brand-solid #1b5344 / fg-brand #24704f / bg-brand-weak #e8f1ec`, 다크 `#2f8a6b / #6fcfa8 / #1a2f27`.
- **나머지 토큰은 SEED 그대로**: gray 00~1000, alpha, blue(정보·포커스), yellow(경고), radius r1~r6, dimension x1~x16, shadow s1~s3, duration d1~d6, 타이포 t1~t13(static px).
- **다크 모드**: `@media (prefers-color-scheme: dark)` 한 블록 + `color-scheme: light dark`. 토글 없음.
- **폰트**: Pretendard Variable(jsDelivr dynamic subset) → 시스템 폰트 폴백.
- **breakpoint**: SEED sm 480 / md 768 / lg 1280. `min-width`만 사용.

## 파일

| 파일 | 역할 |
|---|---|
| `dist/tokens.css` | 토큰 발췌 + 브랜드 오버라이드 + 다크 블록 |
| `dist/app.css` | 레이아웃·컴포넌트 (`minimal.css` 대체) |
| `dist/index.html` | 앱바를 `.shell` 밖으로, 설정 버튼 아이콘화, 필터 select를 `.filters`로 묶음, theme-color·color-scheme 메타 |
| `dist/app.js` | 섹션명 `<span>`에 `badge` 클래스만 추가 |
| `scripts/server.py` | 캐시버스팅 해시 대상 `tokens.css`+`app.css` |

## 레이아웃 규격

- **앱바**: sticky, 56px(md+ 64px), `bg-layer-default`, 아래 `stroke-neutral-muted`. 모바일은 설정이 44×44 아이콘 버튼.
- **툴바**: 모바일은 검색 풀폭 + 날짜/기간/언론사 select 가로 스크롤 한 줄, md+는 `날짜 | 검색(flex) | 기간 | 언론사` 한 줄. 입력 44px, radius r2, inset 1px 테두리, 포커스 2px `stroke-focus-ring`.
- **섹션 칩**: SEED chip solid 36px pill. 모바일 sticky(top 56px) 가로 스크롤, md+ 줄바꿈 + 아래 구분선. 선택은 `bg-brand-solid`.
- **헤드라인**: 표면 카드 안 리스트, 섹션명은 badge(brand weak). 1열 → md 2열.
- **카드**: `bg-layer-default`, radius r4, inset 1px `stroke-neutral-subtle`, 그림자 없음(hover 시 s1). 1열 12px → md 2열 16px → lg 3열 20px. 제목 t6→t7, 요약 t4→t5.
- **배너/상태**: 오늘 보고서 없음 = warning weak, 수집 상태 = informative weak + 3px 진행 막대.
- **키워드 설정**: <768px 바텀시트(radius 상단 r5, `@starting-style`로 아래에서 올라옴), md+ 640px 중앙 다이얼로그.
- 누름 피드백 `scale .96~.97`, hover는 `(hover:hover) and (pointer:fine)`에서만, `prefers-reduced-motion`에서 모두 해제. safe-area inset 반영.

## 검증

`node --check dist/app.js`, `python -m unittest discover -s scripts -p "test_*.py"`(43 OK), Chrome에서 390/768/1440px 및 라이트·다크 확인(가로 스크롤 없음, 헤드라인 → 카드 flash, 관련 보도 토글, 저장함, 설정 바텀시트).
