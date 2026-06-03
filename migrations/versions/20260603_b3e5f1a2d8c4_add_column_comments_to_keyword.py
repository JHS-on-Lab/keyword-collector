"""add_column_comments_to_keyword

keyword 테이블 각 컬럼에 comment 추가.
데이터/스키마 변경 없음 — 가독성 개선만.

Revision ID: b3e5f1a2d8c4
Revises: 9f4a2d1e8c70
Create Date: 2026-06-03
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'b3e5f1a2d8c4'
down_revision: Union[str, None] = '9f4a2d1e8c70'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# (컬럼명, 타입, nullable, comment) — NULL 허용 여부와 타입은 기존과 동일하게 유지
_CHANGES = [
    ("keyword",          "VARCHAR(255)", False, "검색어 또는 식별자. NAVER_STOCK 은 종목코드 (예: 005930)"),
    ("portal_type",      "VARCHAR(20)",  False, "NAVER | DAUM | GOOGLE | WEIBO | NAVER_STOCK"),
    ("interval_seconds", "INT",          False, "수집 주기(초). 기본 86400 = 24시간"),
    ("next_discover_at", "DATETIME",     True,  "다음 수집 예정 시각(UTC). NULL 또는 과거이면 즉시 수집 대상"),
    ("last_cursor",      "VARCHAR(512)", True,  "페이지네이션 재개용 커서. 403 실패 시 저장, 성공 완료 시 NULL 리셋"),
    ("enabled",          "TINYINT(1)",   False, "false = 비활성화. disabled_reason 컬럼에 이유 기록"),
    ("priority",         "INT",          False, "수집 우선순위. 높을수록 먼저 처리 (claim_next ORDER BY priority DESC)"),
    ("display_name",     "VARCHAR(100)", True,  "사람이 읽기 쉬운 라벨. NAVER_STOCK: 종목명, GOOGLE: 다국어 키워드 설명 등"),
    ("disabled_reason",  "VARCHAR(200)", True,  "비활성화 이유. 예: '수동 중지' | '상장폐지' | '연속 5회 403'"),
]


def upgrade() -> None:
    conn = op.get_bind()
    for col, col_type, nullable, comment in _CHANGES:
        null_kw = "NULL" if nullable else "NOT NULL"
        conn.execute(sa.text(
            f"ALTER TABLE keyword MODIFY COLUMN `{col}` {col_type} {null_kw} COMMENT :c"
        ), {"c": comment})


def downgrade() -> None:
    pass   # comment 제거는 불필요
