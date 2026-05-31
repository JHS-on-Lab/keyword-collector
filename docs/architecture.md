# 아키텍처 개요

## 한 문장 요약

키워드를 DB에 등록하면, 발견 워커가 포털에서 URL을 수집하고, 추출 워커가 각 URL의 본문을 스크랩해 파일(또는 Solr)로 저장하는 2단계 파이프라인.

---

## 전체 데이터 흐름

```
[운영자]
    │
    │  add_keyword.py
    ▼
┌──────────┐      ┌──────────────┐      ┌────────────────┐
│ keyword  │      │  Discovery   │      │  article_url   │
│  테이블  │─────▶│   Worker     │─────▶│    테이블      │
│          │      │ (dispatcher) │      │ status=        │
│ 검색어 + │      │              │      │ discovered     │
│ 스케줄   │      │ 네이버/다음/ │      └───────┬────────┘
└──────────┘      │ 구글 스크랩  │              │
                  └──────────────┘              │
                                                │ claim_next()
                                                ▼
                                    ┌──────────────────────┐
                                    │  Extraction Worker   │
                                    │                      │
                                    │ fetch (HTTP/headless)│
                                    │   → extract          │
                                    │   → sink             │
                                    └──────────┬───────────┘
                                               │
                        ┌──────────────────────┼──────────────────────┐
                        ▼                      ▼                      ▼
                   status=stored       status=failed_*         status=dead
                        │
               ┌────────┴────────┐
               ▼                 ▼
          FileSink           SolrSink
       (.jsonl 파일)      (Solr 코어)
```

---

## 핵심 테이블 3개

### `keyword` — 수집 스케줄 관리

무엇을, 어느 포털에서, 얼마 주기로 수집할지 설정한다.

```
id │ keyword  │ portal_type │ interval_seconds │ next_discover_at
───┼──────────┼─────────────┼──────────────────┼──────────────────
 1 │ 삼성전자 │ NAVER       │ 86400 (1일)      │ 2026-06-01 09:00
 2 │ 삼성전자 │ DAUM        │ 86400            │ 2026-06-01 09:10
```

`next_discover_at <= NOW()` 가 되면 발견 워커가 그 키워드를 가져간다.

### `article_url` — 수집 큐 + 처리 이력

발견된 URL이 들어오고, 추출 워커가 처리하면서 상태가 바뀐다.

```
status 흐름:
  discovered → extracting → stored         (정상)
                          → failed_transient → (재시도)
                          → failed_permanent  (포기)
                          → dead             (최대 시도 초과)
```

### `collection_log` — 실행 이력

워커가 한 번 실행될 때마다 1행씩 기록된다. 수집량 추이를 SQL로 확인할 수 있다.

---

## 컴포넌트 맵

```
news_crawler/
│
├── adapters/          ← 포털별 URL 수집 (HTTP 스크랩)
│   ├── naver.py         (sds-comps-base-layout 셀렉터)
│   ├── daum.py          (v.daum.net/v/ URL 패턴)
│   ├── google.py        (Google News RSS 피드)
│   └── weibo.py         (전략 미확정 — 미구현)
│
├── scheduling/        ← 발견 워커 루프
│   └── dispatcher.py
│
├── fetch/             ← URL → HTML
│   ├── http_client.py   (정적 HTTP, 리다이렉트 자동 추적)
│   └── headless.py      (Playwright Chromium, JS 렌더링 필요 시)
│
├── extraction/        ← HTML → 제목·본문
│   ├── extractor.py     (진입점: 규칙 우선, 폴백 LibraryChain)
│   ├── rule_engine.py   (도메인별 CSS/XPath 규칙, TTL 캐시 60s)
│   └── library_chain.py (trafilatura → readability 폴백)
│
├── sink/              ← 결과 저장
│   ├── file_sink.py     (data/{날짜}/{포털}-{worker_id}.jsonl)
│   └── solr_sink.py     (Solr 코어 upsert, url_hash → doc id)
│
├── worker/            ← 추출 워커 루프
│   ├── extraction_worker.py
│   ├── reaper.py        (5분 주기로 타임아웃 extracting 행 회수)
│   └── _healthcheck.py  (heartbeat 시 /tmp/healthcheck 갱신)
│
├── repository/        ← DB 접근
│   ├── keyword_repo.py
│   ├── article_url_repo.py
│   ├── domain_repo.py
│   └── collection_log_repo.py
│
└── domain_logic/      ← 순수 도메인 로직 (DB·네트워크 없음)
    ├── url_normalizer.py  (HTTP→HTTPS, 추적파라미터 제거, SHA256)
    ├── failure_classifier.py (HTTP 코드·예외 → ErrorCode, is_permanent)
    └── backoff.py         (지수 백오프 + jitter)
```

---

## 멀티 워커가 안전한 이유

같은 역할의 워커를 여러 개 동시에 띄워도 같은 작업을 중복 처리하지 않는다.

**발견 워커**: `keyword` 테이블에서 `FOR UPDATE SKIP LOCKED` 로 키워드를 가져간다.  
→ 워커 A가 "삼성전자/NAVER" 를 처리 중이면, 워커 B는 다른 키워드를 가져간다.

**추출 워커**: `article_url` 테이블에서 동일한 방식으로 URL을 하나씩 점유한다.  
→ 여러 워커가 동시에 돌아도 같은 URL을 중복 처리하지 않는다.

---

## 구현 현황

| 기능 | 상태 |
|------|------|
| discovery (naver / daum / google) | 완료 |
| extraction (FileSink / SolrSink) | 완료 |
| headless 렌더링 (Playwright) | 완료 — `domain.render_mode=headless` 설정 필요 |
| 도메인 규칙 엔진 (CSS/XPath, TTL 캐시) | 완료 |
| Reaper (좀비 extracting 자동 회수) | 완료 — extraction 워커 시작 시 daemon 스레드 자동 시작 |
| Docker healthcheck | 완료 — heartbeat마다 `/tmp/healthcheck` 갱신 |
| Weibo discovery | **미구현** — 전략 결정 후 `adapters/weibo.py` 구현 |

---

## 향후 과제

### [ ] RDB 데이터 보관 정책 구현

`article_url` 테이블은 현재 삭제 정책 없이 무한 누적된다.  
**방침: `stored` 상태 레코드는 수집일(`collected_date`) 기준 1개월 후 삭제.**

구현 시 결정해야 할 사항:
- 삭제 단위: `collected_date < NOW() - INTERVAL 1 MONTH` + `status = 'stored'`
- 실행 주체: 별도 cron 스크립트(`scripts/purge_old_articles.py`) 또는 DB 이벤트 스케줄러
- `collection_log`도 동일 기준으로 정리할지 여부
- `url_hash` UNIQUE 제약 — 삭제 후 같은 URL이 재수집되면 다시 `discovered`로 들어옴 (의도된 동작인지 확인)

> `collected_date` 컬럼과 `ix_article_url_claim` 인덱스가 이미 있어 대량 삭제 쿼리 효율은 확보돼 있다.

---

## 관련 문서

| 주제 | 문서 |
|------|------|
| 처음 실행 | [quickstart.md](quickstart.md) |
| 운영 명령어 / SQL | [ops-commands.md](ops-commands.md) |
| 도메인 규칙 설정 | [domain-rules-guide.md](domain-rules-guide.md) |
| 컨테이너 배포 | [deployment.md](deployment.md) |
| 전체 설계 명세 | [news-crawler-design.md](news-crawler-design.md) |
