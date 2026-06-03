# 네이버 · 다음 뉴스 발견 전략

## 네이버 기본 동작

**엔드포인트**
```
GET https://search.naver.com/search.naver
    ?where=news&query={keyword}&sort=1&pd=4&start={offset}
```

| 파라미터 | 값 | 의미 |
|---|---|---|
| `sort` | `1` | 최신순 |
| `pd` | `4` | 1일 이내 (실측값, 공식 문서 없음) |
| `start` | `1 → 11 → 21 → ...` | 페이지네이션 오프셋 |

- 단순 HTTP GET, JS 실행 불필요 (`render_mode=static`)
- 셀렉터: 부모 클래스가 `sds-comps-base-layout` 인 `a[href]` — 빌드마다 해시가 바뀌는 `fender-ui_` 대신 사용
- 반환: 언론사 직접 URL (예: `https://www.mk.co.kr/article/...`)

**페이지 수 설정** (`.env`)
```
NAVER_MAX_PAGES=50   # 키워드당 최대 50페이지 = 최대 500건
```

---

---

## 다음 기본 동작

**엔드포인트**
```
GET https://search.daum.net/search
    ?w=news&q={keyword}&sort=recency&period=d&p={page}
```

| 파라미터 | 값 | 의미 |
|---|---|---|
| `period` | `d` | 1일 이내 (`w`=1주, `m`=1개월) |
| `p` | `1 → 2 → 3 → ...` | 페이지 번호 |

- 단순 HTTP GET, JS 실행 불필요
- 셀렉터: `a[href*="v.daum.net/v/"]` + `class=""` 조건 (썸네일 제외)
- 반환: Daum 뷰어 URL (예: `https://v.daum.net/v/20260603003218841`)
- 다음은 403 레이트리밋 이슈 없음 — 재시도 전략 불필요

**페이지 수 설정** (`.env`)
```
DAUM_MAX_PAGES=10   # 키워드당 최대 10페이지 = 최대 100건
```

---

## 공통 — 페이지네이션 재개 (last_cursor)

`keyword.last_cursor` 컬럼에 마지막으로 시도한 cursor 를 저장한다.

```
1회차
  page 1 (cursor=None)   → 성공, cursor = "start=11"
  page 2 (cursor="start=11") → 403 발생
    → keyword.last_cursor = "start=11"  저장

재시도 (30분 뒤)
  claim_next() 가 last_cursor="start=11" 반환
  page 2 (cursor="start=11") → 성공  ← page 1 재요청 없음
  page 3, 4, ... → 성공
  완료 → keyword.last_cursor = NULL  리셋
```

- page 1 실패 시: `last_cursor=NULL` → 재시도도 page 1부터
- 성공 완료 시: `last_cursor=NULL` → 다음 24h 수집은 항상 page 1부터
- 중복 기사: `url_hash` UNIQUE 로 DB 레벨에서 조용히 무시

---

## 403 실패 전략 (네이버 전용)

### 원인

네이버는 **IP 전체 차단이 아닌 쿼리별 레이트리밋**을 적용한다.
같은 키워드를 연속 여러 페이지 요청 시 403 발생. 다른 키워드 요청은 정상인 경우가 많다.

```
keyword A: page 1 성공 → page 2 403
keyword B: page 1 성공  ← 다른 쿼리라서 OK
```

### 재시도 흐름

```
403 발생
  ↓
keyword.last_cursor = 실패한 cursor 저장
collection_log 에 error_msg = "HTTPStatusError: 403..." 기록

오늘 403 횟수 조회 (collection_log COUNT)
  ├─ count < 5  → keyword.next_discover_at = NOW() + 30분 (reschedule)
  │               WARNING: "attempt=N/5 — retry at HH:MM UTC"
  │               다음 키워드 계속 처리 (강제 sleep 없음)
  └─ count >= 5 → 포기, next_discover_at 는 claim_next 시 설정한 +24h 유지
                  WARNING: "gave up after 5 attempts — next try in 24h"
```

### 재시도 횟수 근거

메모리가 아닌 `collection_log` 에서 집계하므로 **워커 재시작에도 카운트가 유지**된다.

```sql
SELECT COUNT(*)
FROM collection_log
WHERE keyword_id = :kid
  AND error_msg LIKE '%403%'
  AND run_date = CURDATE()   -- UTC 기준
```

4회차 시도 직전: rows=3, 3 < 5 → 재시도  
5회차 시도 직전: rows=4, 4 < 5 → 재시도  
6회차 시도 직전: rows=5, 5 >= 5 → 포기

### 200 + 빈 HTML

403 대신 200으로 차단 페이지를 반환하는 경우.

```
GET → 200, 하지만 sds-comps-base-layout 셀렉터에 매칭 없음 → urls=[]
  ↓
WARNING [adapter] naver 0 urls keyword='...' page=N
collection_log: urls_found=0, error_msg=NULL (정상 처리)
```

에러로 간주하지 않음. 0건 수집은 그날 뉴스가 없는 정상 케이스도 있음.

---

## Idle 주기

처리할 due 키워드가 없으면 **60초마다** DB 를 재확인한다.
30분 reschedule 된 키워드는 최대 30분 1초 이내에 재수집이 시작된다.

```python
_IDLE_SLEEP_SEC = 60   # dispatcher.py
```

---

## 실행

```bash
# 워커 (무한 루프, 전 키워드 순환)
.venv\Scripts\python.exe -m news_crawler --role discovery --portal naver

# 단일 키워드 수동 실행
.venv\Scripts\python.exe scripts\run_discovery.py --keyword "삼성전자" --portal NAVER --pages 10
```

---

## 모니터링

```sql
-- 오늘 403 에러 현황
SELECT k.keyword, cl.urls_found, cl.error_msg, cl.started_at
FROM collection_log cl
JOIN keyword k ON k.id = cl.keyword_id
WHERE cl.run_type = 'discovery'
  AND cl.run_date = CURDATE()
  AND cl.error_msg IS NOT NULL
ORDER BY cl.started_at DESC;

-- 403 재시도 대기 중인 키워드 (next_discover_at 이 30분 이내)
SELECT keyword, display_name, next_discover_at, last_cursor
FROM keyword
WHERE portal_type = 'NAVER'
  AND next_discover_at BETWEEN NOW() AND NOW() + INTERVAL 30 MINUTE;

-- 오늘 포털별 수집 성공률
SELECT
    portal_type,
    COUNT(*)                           AS total_runs,
    SUM(error_msg IS NOT NULL)         AS failed_runs,
    ROUND(AVG(urls_found), 1)          AS avg_urls_found
FROM collection_log
WHERE run_type = 'discovery' AND run_date = CURDATE()
GROUP BY portal_type;
```
