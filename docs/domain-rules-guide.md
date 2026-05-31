# 도메인 규칙 가이드

`domain` 테이블은 언론사 도메인별 수집 정책을 저장한다.  
**행이 없는 도메인은 전역 기본값을 쓰므로, 특별히 설정이 필요한 도메인만 등록하면 된다.**

---

## 1. 설정 가능한 항목

| 컬럼 | 설명 | 기본값 |
|------|------|--------|
| `crawl_delay_ms` | 이 도메인에 요청 사이 최소 대기 시간 (ms) | `DEFAULT_CRAWL_DELAY_MS` (.env, 기본 1000ms) |
| `render_mode` | 본문 추출 방식 | `static` (정적 HTTP) |
| `cooldown_until` | 차단 해제 시각. 이 시각 전까지 요청 안 함 | NULL (차단 없음) |
| `rules_json` | 도메인 전용 CSS/XPath 추출 규칙 (Phase C 이후 사용) | NULL (라이브러리 자동 추출) |

---

## 2. 설정 명령어

```bash
# 현재 설정 조회
python scripts/add_domain_rule.py --host www.example.com --show

# crawl_delay 설정
python scripts/add_domain_rule.py --host www.example.com --delay 3000

# render_mode 변경
python scripts/add_domain_rule.py --host www.example.com --render headless

# 쿨다운 해제 (차단이 풀렸을 때)
python scripts/add_domain_rule.py --host www.example.com --cooldown-clear
```

---

## 3. 언제 설정하나

### crawl_delay_ms — 서버가 429를 반복할 때

```bash
# 기본(1초)에서 3초로 늘림
python scripts/add_domain_rule.py --host www.chosun.com --delay 3000
```

**판단 기준:**
- `article_url` 테이블에서 해당 호스트의 `last_error_code = 'FETCH_429'` 가 반복되면 딜레이를 늘린다.
- 반대로 수집이 원활하면 줄여도 된다.

```sql
-- 429 자주 나는 도메인 확인
SELECT host, COUNT(*) AS cnt
FROM article_url
WHERE last_error_code = 'FETCH_429'
GROUP BY host ORDER BY cnt DESC;
```

---

### render_mode = headless — 본문이 계속 비어 나올 때

정적 HTTP 로는 빈 HTML 만 오는 사이트 (JS 렌더링 필요)에 설정한다.

```bash
python scripts/add_domain_rule.py --host www.example.com --render headless
```

> **주의**: `headless` 모드는 Phase C 이후 지원된다. 현재는 설정해도 동작하지 않으며
> Playwright 구현(`fetch/headless.py`) 완료 후 활성화된다.

**headless 가 필요한 징후:**
- `last_error_code = 'PARSE_ERROR'` 또는 `BODY_TOO_SHORT'` 가 해당 도메인에서만 반복됨
- 브라우저로 직접 열면 본문이 보이는데 크롤러는 빈 결과를 반환함

```sql
-- PARSE_ERROR 많은 도메인 (headless 후보)
SELECT host, COUNT(*) AS cnt
FROM article_url
WHERE last_error_code IN ('PARSE_ERROR', 'BODY_TOO_SHORT')
GROUP BY host ORDER BY cnt DESC LIMIT 20;
```

---

### cooldown — 수동 차단 해제

추출 워커가 429 또는 5xx 를 연속 감지하면 자동으로 `cooldown_until` 을 설정한다.  
쿨다운이 지나면 자동 해제되지만, 긴급하게 수동으로 해제할 때 사용한다.

```bash
python scripts/add_domain_rule.py --host www.example.com --cooldown-clear
```

---

## 4. 시스템이 자동으로 관리하는 항목 (직접 수정 불필요)

| 컬럼 | 의미 | 업데이트 시점 |
|------|------|--------------|
| `success_rate` | 최근 추출 성공률 (0~1, EMA 방식) | 추출할 때마다 자동 갱신 |
| `avg_body_len` | 평균 본문 길이 (EMA) | 추출할 때마다 자동 갱신 |
| `recent_fail_count` | 최근 연속 실패 횟수 | 추출할 때마다 자동 갱신 |
| `cooldown_until` | 차단 해제 시각 | 429 등 감지 시 자동 설정 |

이 값들은 운영 모니터링용으로, 직접 수정할 필요는 없다.

```sql
-- 문제 있는 도메인 한눈에 보기
SELECT host, success_rate, avg_body_len, recent_fail_count, cooldown_until
FROM domain
WHERE success_rate < 0.5 OR recent_fail_count >= 3
ORDER BY recent_fail_count DESC;
```

---

## 5. rules_json — 도메인 전용 추출 규칙

`rules_json` 을 설정하면 trafilatura/readability 보다 먼저 시도된다.  
규칙이 실패하면 자동으로 라이브러리 체인으로 폴백하므로 안전하다.

### 형식

```json
{
  "title":  {"css": "h1.article-title"},
  "body":   {"css": "div.article-body p"},
  "author": {"css": "span.byline"},
  "press":  {"xpath": "//meta[@property='og:site_name']/@content"}
}
```

- `css` — CSS 셀렉터 (selectolax 사용). 여러 노드가 매칭되면 줄바꿈으로 이어 붙인다.
- `xpath` — XPath 표현식 (lxml 사용). 속성값(`//@attr`)과 텍스트(`//tag`) 모두 지원.
- 필드는 `title`, `body`, `author`, `press` 를 지원한다. 일부만 지정해도 된다.

### 등록 방법

현재 `add_domain_rule.py` 는 `--delay`, `--render` 만 지원하므로 `rules_json` 은 SQL 로 직접 등록한다:

```sql
INSERT INTO domain (host, rules_json, rules_enabled, updated_by)
VALUES (
  'www.chosun.com',
  '{"title": {"css": "h1.article-tit"}, "body": {"css": "div.article-body"}}',
  true,
  'manual'
)
ON DUPLICATE KEY UPDATE
  rules_json    = VALUES(rules_json),
  rules_enabled = true,
  updated_by    = 'manual';
```

### 규칙 캐시

규칙은 메모리에 캐시된다 (`RULES_CACHE_TTL_SECONDS`, 기본 60초).  
DB 에서 규칙을 수정하면 최대 60초 후 자동 반영된다. 재배포 불필요.

### 셀렉터 찾는 법

브라우저 개발자 도구(F12) → Elements 탭 → 본문 영역 우클릭 → "Copy selector" 로 CSS 셀렉터를 확인한다.

---

## 6. 전체 domain 현황 조회

```sql
SELECT
    host,
    crawl_delay_ms,
    render_mode,
    ROUND(success_rate * 100, 1)  AS success_pct,
    avg_body_len,
    recent_fail_count,
    cooldown_until,
    updated_at
FROM domain
ORDER BY recent_fail_count DESC, updated_at DESC;
```
