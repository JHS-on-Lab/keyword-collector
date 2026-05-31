# keyword 통계 컬럼 → collection_log 이전 결정 기록

> 상태: **완료** (마이그레이션 `005c8266bfd3`)
> 작성일: 2026-05-31

---

## 결정 요약

`keyword` 테이블에 추가했던 `last_discovery_url_count`, `last_discovery_duration_ms` 두 컬럼을
제거하고, 같은 정보를 `collection_log` 테이블에 런 단위로 저장한다.

---

## 경위

1. **초기 설계**: 발견 완료 후 통계를 `keyword` 테이블에 직접 기록
   (`last_discovery_url_count`, `last_discovery_duration_ms` 컬럼 추가 — 마이그레이션 `fa7e8223276a`)

2. **문제 인식**: `keyword` 테이블에 두면 마지막 실행 결과만 남는다.
   - 어제 50건이었는데 오늘 5건이 된 이유를 알 수 없음
   - 실패 시 컬럼이 갱신되지 않아 "성공인지 실패인지" 구분 불가
   - 포털별·날짜별 추이 조회가 불가능

3. **결정**: `collection_log` 테이블을 별도 생성해 런 단위로 저장
   (마이그레이션 `a984ac3bc00b`)하고 `keyword` 통계 컬럼 제거
   (마이그레이션 `005c8266bfd3`)

---

## 현재 구조

| 테이블 | 저장 내용 |
|--------|-----------|
| `keyword` | `last_discovered_at` — 마지막 성공 시각만 보존 |
| `collection_log` | 런마다 1행: `urls_found`, `urls_inserted`, `urls_skipped`, `duration_ms`, `error_msg` |

`collection_log`를 쓰면:
- 날짜별·포털별 수집량 추이 조회 가능
- 실패 런도 `error_msg` 와 함께 행으로 남음 (발견된 이슈 3.2에서 추가)
- `keyword` 테이블이 스케줄 관리에만 집중

---

## 마이그레이션 순서

```
fa7e8223276a  add_discovery_stats_to_keyword   (last_discovery_* 추가)
a984ac3bc00b  add_collection_log               (collection_log 생성)
005c8266bfd3  drop_discovery_stats_from_keyword (last_discovery_* 제거)
ad50ec2c6f6c  add_error_msg_to_collection_log  (error_msg 추가)
```
