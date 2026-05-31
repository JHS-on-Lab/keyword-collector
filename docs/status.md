# 프로젝트 현황

_최종 갱신: 2026-05-31 (Phase A·B·C 완료)_

---

## 1. 구현 완료

### 1.1 인프라 / 공통

| 파일 | 내용 |
|------|------|
| `types.py` | `PortalType` · `ArticleStatus` · `RenderMode` · `ErrorCode` Enum, 핵심 데이터클래스 |
| `ports.py` | `SourceAdapter` · `Fetcher` · `Extractor` · `Sink` Protocol |
| `config.py` | 환경변수 로딩 + `validate()` — RDS·터널·Solr 필수 변수 일괄 검증 |
| `logging_setup.py` | `app.log` (INFO+) / `error.log` (WARNING+) 이중 스트림, 일별 로테이션 |
| `__main__.py` | `config.validate()` → `logging_setup.setup()` → 워커 루프 (extraction 시 Reaper 데몬 스레드 자동 시작) |
| `fetch/_client.py` | 공통 User-Agent + `make_client()` — 어댑터·Fetcher 모두 사용 |

### 1.2 DB / 마이그레이션

| 파일 | 내용 |
|------|------|
| `repository/db.py` | SSH 터널 옵션 + SQLAlchemy 엔진 (`pool_pre_ping`, `pool_recycle=1800`) |
| `repository/keyword_repo.py` | `claim_next()` — `FOR UPDATE SKIP LOCKED` + 즉시 `next_discover_at` 갱신 |
| `repository/article_url_repo.py` | 발견: `bulk_insert_discovered` / 추출: `claim_next` · `mark_stored` · `mark_failed` · `mark_dead` / 운영: `recover_timed_out` · `requeue` |
| `repository/domain_repo.py` | `get` · `upsert_health` · `set_cooldown` — sparse 테이블 |
| `repository/collection_log_repo.py` | discovery · extraction 런 이력, `error_msg` 로 발견 런 실패 이유 기록 |
| `migrations/` | 5개 버전 — keyword · article_url · domain · collection_log · error_msg |

### 1.3 발견 파이프라인

| 파일 | 내용 |
|------|------|
| `adapters/_base.py` | `PaginatedAdapter` — period · max_pages · delay_ms 공통 베이스 |
| `adapters/naver.py` | `sds-comps-base-layout` 부모 클래스 기반, 0건 시 WARNING |
| `adapters/daum.py` | `v.daum.net/v/` URL 패턴, p 파라미터 페이지네이션 |
| `adapters/google.py` | Google News RSS, `pubDate` 날짜 필터, 최대 ~100건 |
| `scheduling/dispatcher.py` | 키워드 루프 + 페이지 단위 flush + `collection_log` 기록 |

### 1.4 추출 파이프라인

| 파일 | 내용 |
|------|------|
| `fetch/http_client.py` | `HttpFetcher` — 동기 httpx, `follow_redirects=True`, 4xx/5xx 예외 없이 반환 |
| `fetch/headless.py` | `HeadlessFetcher` — Playwright Chromium, 브라우저 인스턴스 재사용 (`playwright install chromium` 필요) |
| `fetch/rate_limit.py` | `RateLimiter` — host별 딜레이, `DomainRepo` 에서 `crawl_delay_ms` 읽음 |
| `extraction/rule_engine.py` | `RuleEngine` — CSS/XPath 규칙 추출, TTL 캐시 60초 (DB 수정 시 재배포 불필요) |
| `extraction/library_chain.py` | `LibraryChain` — trafilatura 1차 → readability 폴백, 본문 200자 미만 BODY_TOO_SHORT |
| `extraction/extractor.py` | `DefaultExtractor` — 규칙 우선, 폴백 LibraryChain. `domain_repo` 주입 시 규칙 활성화 |
| `sink/__init__.py` | `make_sink()` — `SINK_TYPE` 환경변수로 FileSink / SolrSink 선택 |
| `sink/file_sink.py` | `FileSink` — `data/{YYYY-MM-DD}/{portal}.jsonl` append |
| `sink/solr_sink.py` | `SolrSink` — `SOLR_URL` / `SOLR_BATCH_SIZE` config 사용, 배치 upsert |
| `worker/extraction_worker.py` | `run_extraction_loop()` — `render_mode` 에 따라 정적/headless 분기, 규칙 엔진 활성화 |
| `worker/reaper.py` | 5분 주기로 `extracting` 타임아웃 행을 `discovered` 로 회수 |

`article_url` 상태 전이:

```
discovered
    │
    ▼ claim_next()
extracting ──── (워커 정상 종료)
    │                   ↓
    │              stored  ← 성공
    │
    ├── HTTP 4xx/403/404   → failed_permanent (재시도 없음)
    ├── HTTP 429/5xx, 타임아웃 → failed_transient (next_retry_at 후 자동 재시도)
    ├── attempt >= MAX_ATTEMPTS → dead
    └── Reaper: claimed_at 초과 → discovered 복구
```

`failed_transient` 재시도: `claim_next()` 호출 시 `next_retry_at <= NOW()` 이면 자동 픽업.  
백오프: `30s * 2^attempt + jitter`, 최대 3600s.

### 1.5 운영 안전장치

| 파일 | 내용 |
|------|------|
| `worker/reaper.py` | `extracting` + `claimed_at > CLAIM_TIMEOUT_SECONDS` → `discovered` 강제 회수, 5분 주기 |
| `repository/article_url_repo.py` | `recover_timed_out()` (reaper용) · `requeue()` (수동 재투입용) |

### 1.6 도메인 로직

| 파일 | 내용 |
|------|------|
| `domain_logic/url_normalizer.py` | HTTP→HTTPS, 추적 파라미터 제거, SHA256 해시 |
| `domain_logic/failure_classifier.py` | HTTP 상태코드·예외 → `(ErrorCode, is_permanent)` |
| `domain_logic/backoff.py` | `base * 2^attempt + jitter`, 최대 `BACKOFF_MAX_SECONDS` |
| `fetch/proxy.py` | `ProxyProvider` Protocol + `DirectProxy` (프록시 없음) |

### 1.7 스크립트 (운영용 9개)

| 파일 | 목적 |
|------|------|
| `scripts/check_db.py` | SSH 터널 + RDS 연결 확인 |
| `scripts/check_solr.py` | Solr 연결·코어 상태·스키마 필드 확인 |
| `scripts/verify_schema.py` | 테이블·인덱스·SKIP LOCKED 동작 확인 |
| `scripts/add_keyword.py` | 키워드 등록·수정 |
| `scripts/add_domain_rule.py` | 도메인 정책 설정 (`--delay`, `--render`, `--cooldown-clear`) |
| `scripts/run_discovery.py` | 특정 키워드 수동 발견 → DB 저장 |
| `scripts/run_extraction.py` | discovered URL 수동 추출 → Sink |
| `scripts/requeue_failed.py` | 실패 URL 재투입 (`--status`, `--host`, `--error-code`) |
| `scripts/preview_adapter.py` | DB 저장 없이 어댑터 URL 목록 미리보기 |

---

## 2. 미구현 (Phase D)

| 파일 | 내용 |
|------|------|
| `adapters/weibo.py` | 전략 미확정 — 구현 전 `docs/decisions/weibo-discovery.md` 먼저 작성 |

---

## 3. 할일

```
[ ] adapters/weibo.py — 전략 결정 후 구현
      docs/decisions/weibo-discovery.md 먼저 작성
```

---

## 4. 해결된 이슈 이력

| 이슈 | 해결 방법 |
|------|-----------|
| 네이버 `fender-ui_` 셀렉터 취약성 | `sds-comps-base-layout` 부모 클래스로 교체, 0건 시 WARNING |
| 발견 실패 이유 DB 미기록 | `collection_log.error_msg` 추가 (마이그레이션 `ad50ec2c6f6c`) |
| `make_adapter()` 실패 시 NameError | `total_found = 0` 초기화를 `try:` 밖으로 이동 |
| `claim_next()` 실패 시 워커 전체 종료 | while 루프 안 `try/except` + sleep/continue |
| 로그 `component` 항상 `app` | dispatcher `extra` 에 `"component": "dispatcher"` 추가 |
| `config.py` 필수 변수 검증 없음 | `validate()` 추가 — 누락 목록 출력 후 exit |
| 스크립트에서 `error.log` 미기록 | `logging.basicConfig()` → `logging_setup.setup()` 교체 |
| 마이그레이션 롤백 결정 미문서화 | [decisions/collection-log-migration.md](decisions/collection-log-migration.md) 작성 |
| 어댑터 3개에 User-Agent 중복 | `fetch/_client.py` `make_client()` 로 통합 |
| `failed_transient` 재시도 안 됨 | `claim_next()` WHERE 절에 `failed_transient + next_retry_at <= NOW()` 추가 |
| JSONL `keyword` 필드 공백 | `claim_next()` 에서 keyword 테이블 JOIN |
| `_flush_log` duration_ms 절대값 오류 | `batch_start_mono` 로 배치 기준 상대값 계산 |
| `_process_one` dict 뮤테이션으로 결과 전달 | `bool` 반환으로 변경 |
| `_handle_failure` 조건 중복·순서 모호 | MAX_ATTEMPTS → permanent → transient 명확화 |
| `rate_limit.py` 첫 요청 huge sleep | `last is None` 이면 즉시 통과 |
| `ports.py` `Extractor` 시그니처 불일치 | `portal_type`, `keyword` 파라미터 추가 |
| `failure_classifier.py` 400/401 미처리 | `FETCH_403` 영구로 분류 추가 |
| naver/daum `__init__`·delay·max_pages 중복 | `adapters/_base.py` `PaginatedAdapter` 추출 |
| `HeadlessFetcher` 매 URL 마다 브라우저 재시작 | 루프 레벨에서 한 번만 생성, `_process_one` 에 전달해 재사용 |
| `SolrSink` `os.getenv` 직접 사용·`__del__` 플러시 | `config` 경유, `__enter__`/`__exit__` 컨텍스트 매니저로 교체 |
| `SOLR_URL`·`SOLR_BATCH_SIZE` config 미정의 | 추가. `validate()` 에 `SINK_TYPE=solr` 시 `SOLR_URL` 필수 검증 추가 |
| Sink 선택 하드코딩 | `sink/__init__.py` `make_sink()` 팩토리로 `SINK_TYPE` 환경변수 분기 |

---

## 5. 실행 가능 여부

| 기능 | 상태 |
|------|------|
| `--role discovery --portal naver/daum/google` | **가능** |
| `--role extraction` (FileSink) | **가능** |
| `--role extraction` (SolrSink) | **가능** — `SINK_TYPE=solr`, `SOLR_URL` 설정 필요 |
| Reaper (자동 회수) | **가능** — extraction 워커 시작 시 자동 실행 |
| 규칙 기반 추출 | **가능** — `domain.rules_json` 설정 시 자동 적용 |
| Headless 렌더링 | **가능** — `playwright install chromium` 후 `domain.render_mode=headless` 설정 |
| Weibo 발견 | **불가** — 전략 미확정 |
