"""drop_last_discovered_at_from_keyword

keyword.last_discovered_at 는 collection_log 로 완전히 대체 가능한 중복 필드.
마지막 성공 수집 시각은 다음 쿼리로 조회한다:
  SELECT MAX(started_at) FROM collection_log
  WHERE keyword_id = :kid AND run_type = 'discovery' AND error_msg IS NULL

Revision ID: 9f4a2d1e8c70
Revises: c1d7f3a8e2b5
Create Date: 2026-06-03
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '9f4a2d1e8c70'
down_revision: Union[str, None] = 'c1d7f3a8e2b5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column('keyword', 'last_discovered_at')


def downgrade() -> None:
    op.add_column(
        'keyword',
        sa.Column('last_discovered_at', sa.DateTime(), nullable=True),
    )
