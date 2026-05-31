"""
keyword 테이블 접근.

keyword 는 수집 스케줄을 담당한다.
next_discover_at 이 현재 시각보다 과거이면 "수집할 때가 됐다"는 뜻이다.

claim_next() 의 동작 원리:
  1. next_discover_at <= NOW() 인 키워드를 FOR UPDATE SKIP LOCKED 로 잠근다.
     → 다른 워커가 동시에 같은 키워드를 가져가는 것을 막는다.
  2. 잠그는 즉시, 같은 트랜잭션 안에서 next_discover_at 을 24시간 뒤로 밀어둔다.
     → 트랜잭션이 끝난 뒤에도 다른 워커가 다시 집어가지 않는다.
"""

from __future__ import annotations

from datetime import datetime
from sqlalchemy import Engine, text


class KeywordRepo:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def claim_next(self, portal: str, worker_id: str) -> dict | None:
        """
        due 상태(enabled + next_discover_at <= NOW())인 키워드를
        SKIP LOCKED로 원자적으로 점유하고 next_discover_at을 즉시 갱신한다.

        반환: {id, keyword, portal_type, interval_seconds} 또는 None(없으면)
        """
        portal_filter = "" if portal.upper() == "ALL" else "AND portal_type = :portal"

        with self._engine.begin() as conn:
            row = conn.execute(
                text(f"""
                    SELECT id, keyword, portal_type, interval_seconds
                    FROM keyword
                    WHERE enabled = true
                      AND (next_discover_at IS NULL OR next_discover_at <= NOW())
                      {portal_filter}
                    ORDER BY priority DESC, next_discover_at ASC
                    LIMIT 1
                    FOR UPDATE SKIP LOCKED
                """),
                {"portal": portal.upper()},
            ).fetchone()

            if row is None:
                return None

            kw = dict(row._mapping)

            # 즉시 next_discover_at 갱신 → 다른 워커가 재점유 불가
            conn.execute(
                text("""
                    UPDATE keyword
                    SET next_discover_at = NOW() + INTERVAL :sec SECOND
                    WHERE id = :kid
                """),
                {"sec": kw["interval_seconds"], "kid": kw["id"]},
            )

        return kw

    def complete(self, keyword_id: int) -> None:
        """발견 완료 후 last_discovered_at 기록. 상세 통계는 collection_log에 저장."""
        with self._engine.begin() as conn:
            conn.execute(
                text("UPDATE keyword SET last_discovered_at = NOW() WHERE id = :kid"),
                {"kid": keyword_id},
            )

    def list_all(self, portal: str = "ALL") -> list[dict]:
        """전체 키워드 목록 조회 (운영 확인용)."""
        portal_filter = "" if portal.upper() == "ALL" else "WHERE portal_type = :portal"
        with self._engine.connect() as conn:
            rows = conn.execute(
                text(f"""
                    SELECT id, keyword, portal_type, enabled,
                           last_discovered_at, next_discover_at, priority
                    FROM keyword
                    {portal_filter}
                    ORDER BY portal_type, keyword
                """),
                {"portal": portal.upper()},
            ).fetchall()
        return [dict(r._mapping) for r in rows]
