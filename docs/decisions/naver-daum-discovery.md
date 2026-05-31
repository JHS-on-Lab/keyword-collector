# 네이버 · 다음 뉴스 발견 방식 결정 기록

> 상태: **구현 완료 (정적 HTTP)** / 셀렉터 안정화 완료
> 작성일: 2026-05-31 / 최종 갱신: 2026-05-31

---

## 1. 현재 구현 방식

### 네이버

**엔드포인트**
```
GET https://search.naver.com/search.naver
    ?where=news&query={keyword}&sort=1&pd=4&start={offset}
```

- `sort=1` = 최신순, `pd=4` = 1일 이내 (실측값)
- `start` 파라미터로 페이지네이션: 1 → 11 → 21 → ...
- 단순 HTTP GET, JS 실행 불필요
- 기사 링크 추출: 부모 클래스가 `sds-comps-base-layout` 인 `a[href]` + 차단 호스트 제외 + 경로 있음 조건
  - 네이버 SDS(Smart Design System) 클래스로, 빌드마다 해시가 바뀌는 `fender-ui_` 대신 사용
  - 기사당 정확히 1개의 링크를 선택 (중복 없음)
  - 0개 반환 시 `WARNING` 로그 출력

**기사 URL 형태**
- 언론사 직접 URL (예: `https://www.mk.co.kr/article/...`)

### 다음

**엔드포인트**
```
GET https://search.daum.net/search
    ?w=news&q={keyword}&sort=recency&period=d&p={page}
```

- `sort=recency` = 최신순, `period=d` = 1일 이내
- `p` 파라미터로 페이지네이션: 1 → 2 → 3 → ...
- 단순 HTTP GET, JS 실행 불필요
- 기사 링크 추출: `a[href*="v.daum.net/v/"]` + `class=""` 조건

**기사 URL 형태**
- Daum 뷰어 URL (예: `http://v.daum.net/v/20260531003218841`)

---

## 2. 안정성 평가

| 항목 | 네이버 | 다음 |
|---|---|---|
| 페이지네이션 방식 | 서버 사이드 (`start`) — 안정 | 서버 사이드 (`p`) — 안정 |
| 기사 링크 셀렉터 | `sds-comps-base-layout` 부모 클래스 기반 — **안정** | URL 패턴 기반 (`v.daum.net/v/`) — 상대적으로 안정 |
| JS 렌더링 필요 여부 | 현재 불필요 | 현재 불필요 |
| 차단·캡차 위험 | 낮음 (요청 간격 유지 시) | 낮음 |
| webdriver 필요 여부 | 현재 불필요 | 현재 불필요 |

---

## 3. 알려진 리스크

### 네이버 — 셀렉터 (해결됨)

~~`fender-ui_` 해시 클래스 의존 → 배포마다 변경 위험~~ → **`sds-comps-base-layout`으로 교체 완료**

`sds-comps-*` 는 네이버 SDS(Smart Design System)의 구조 클래스로, 해시 기반 유틸리티 클래스보다 훨씬 안정적.  
SDS 자체가 변경되는 경우 `_parse_urls`가 WARNING을 남기므로 즉시 감지 가능.

### 네이버 — `pd` 파라미터 의미 변경 가능성

- `pd=4`가 1일이라는 건 실측값이며 공식 문서가 없음
- 네이버 서버 변경 시 의미가 달라질 수 있음
- 정기적으로 수집된 기사의 발행일 분포를 확인해야 함

### 다음 — URL 구조 변경 가능성

- `v.daum.net/v/{id}` 패턴이 변경되면 셀렉터 수정 필요
- 네이버보다 리스크는 낮으나 모니터링 필요

---

## 4. 미결 사항

### 4-1. webdriver 전환 기준

어떤 조건이 되면 정적 HTTP 대신 webdriver로 전환할 것인가.

**현재 판단**: 네이버·다음 모두 정적 HTTP로 안정적이므로 webdriver는 도입하지 않는다.  
**전환 검토 조건**: 정적 HTTP 방식이 지속적으로 실패하거나 구조적으로 JS 렌더링이 강제될 때.

→ **조건 발생 전까지 현행 유지**

---

## 5. 모니터링 권장 쿼리

```sql
-- 최근 7일 키워드별 수집량 추이 (급감 감지용)
SELECT
    run_date,
    k.keyword,
    cl.portal_type,
    cl.urls_found
FROM collection_log cl
JOIN keyword k ON k.id = cl.keyword_id
WHERE cl.run_type = 'discovery'
  AND cl.run_date >= CURDATE() - INTERVAL 7 DAY
ORDER BY k.keyword, cl.portal_type, cl.run_date;

-- 오늘 수집량이 0인 키워드 (셀렉터 파손 의심)
SELECT k.keyword, cl.portal_type, cl.urls_found, cl.started_at
FROM collection_log cl
JOIN keyword k ON k.id = cl.keyword_id
WHERE cl.run_type = 'discovery'
  AND cl.run_date = CURDATE()
  AND cl.urls_found = 0;
```
