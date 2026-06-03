"""add_display_name_and_disabled_reason_to_keyword

keyword.display_name    — 사람이 읽기 쉬운 라벨
                          (NAVER_STOCK: "005930" → "삼성전자",
                           GOOGLE: "三星电子" → "삼성전자 (중문)")
keyword.disabled_reason — enabled=false 일 때 비활성화 이유
                          ("상장폐지", "연속 0건", "수동" 등)

Revision ID: c1d7f3a8e2b5
Revises: ad50ec2c6f6c
Create Date: 2026-06-02
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'c1d7f3a8e2b5'
down_revision: Union[str, None] = 'ad50ec2c6f6c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'keyword',
        sa.Column('display_name', sa.String(length=100), nullable=True,
                  comment='사람이 읽기 쉬운 라벨 (종목명, 검색어 설명 등)'),
    )
    op.add_column(
        'keyword',
        sa.Column('disabled_reason', sa.String(length=200), nullable=True,
                  comment='enabled=false 일 때 비활성화 이유'),
    )


def downgrade() -> None:
    op.drop_column('keyword', 'disabled_reason')
    op.drop_column('keyword', 'display_name')
