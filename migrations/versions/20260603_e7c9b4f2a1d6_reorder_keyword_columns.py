"""reorder_keyword_columns

컬럼을 논리적 그룹으로 재정렬한다.
  식별    : id, keyword, portal_type, display_name
  상태    : enabled, disabled_reason, priority
  스케줄  : interval_seconds, next_discover_at, last_cursor

데이터·인덱스·제약 변경 없음.

Revision ID: e7c9b4f2a1d6
Revises: b3e5f1a2d8c4
Create Date: 2026-06-03
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'e7c9b4f2a1d6'
down_revision: Union[str, None] = 'b3e5f1a2d8c4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# (컬럼명, DDL 타입, NULL 허용, DEFAULT, AFTER, comment)
_ORDER = [
    ("display_name",     "VARCHAR(100)", "NULL",     None,    "portal_type",
     "사람이 읽기 쉬운 라벨. NAVER_STOCK: 종목명, GOOGLE: 다국어 키워드 설명 등"),
    ("enabled",          "TINYINT(1)",   "NOT NULL", "1",     "display_name",
     "false = 비활성화. disabled_reason 컬럼에 이유 기록"),
    ("disabled_reason",  "VARCHAR(200)", "NULL",     None,    "enabled",
     "비활성화 이유. 예: '수동 중지' | '상장폐지' | '연속 5회 403'"),
    ("priority",         "INT",          "NOT NULL", "0",     "disabled_reason",
     "수집 우선순위. 높을수록 먼저 처리 (claim_next ORDER BY priority DESC)"),
    ("interval_seconds", "INT",          "NOT NULL", "86400", "priority",
     "수집 주기(초). 기본 86400 = 24시간"),
    ("next_discover_at", "DATETIME",     "NULL",     None,    "interval_seconds",
     "다음 수집 예정 시각(UTC). NULL 또는 과거이면 즉시 수집 대상"),
    ("last_cursor",      "VARCHAR(512)", "NULL",     None,    "next_discover_at",
     "페이지네이션 재개용 커서. 403 실패 시 저장, 성공 완료 시 NULL 리셋"),
]


def upgrade() -> None:
    conn = op.get_bind()
    for col, col_type, null_kw, default, after, comment in _ORDER:
        default_clause = f"DEFAULT {default}" if default is not None else ""
        conn.execute(sa.text(
            f"ALTER TABLE keyword MODIFY COLUMN `{col}` {col_type} {null_kw} "
            f"{default_clause} COMMENT :c AFTER `{after}`"
        ), {"c": comment})


def downgrade() -> None:
    pass  # 순서 복원은 불필요
