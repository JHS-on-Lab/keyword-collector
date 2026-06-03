# keyword 통계 → collection_log 이전

## 결정 요약

`keyword` 테이블에 있던 `last_discovery_url_count`, `last_discovery_duration_ms` 컬럼을 제거하고,
런 단위 통계를 `collection_log` 테이블에 저장한다.

## 이유

`keyword` 테이블에 두면 마지막 실행 결과만 남는다.

- 어제 50건 → 오늘 5건이 된 원인을 알 수 없음
- 실패 시 컬럼이 갱신되지 않아 성공/실패 구분 불가
- 포털별·날짜별 추이 조회 불가능

## 현재 구조

| 테이블 | 저장 내용 |
|--------|-----------|
| `keyword` | 스케줄 설정 (`interval_seconds`, `next_discover_at`, `enabled` 등). 실행 이력 없음. |
| `collection_log` | 런마다 1행: `urls_found`, `urls_inserted`, `urls_skipped`, `duration_ms`, `error_msg` |

`keyword.last_discovered_at` 은 2026-06-03 마이그레이션(`9f4a2d1e8c70`)으로 제거됐다.  
마지막 성공 수집 시각은 `collection_log`에서 조회한다:
```sql
SELECT MAX(started_at) FROM collection_log
WHERE keyword_id = :kid AND run_type = 'discovery' AND error_msg IS NULL;
```
