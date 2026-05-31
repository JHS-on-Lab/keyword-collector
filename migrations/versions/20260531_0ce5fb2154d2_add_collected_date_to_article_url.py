"""add_collected_date_to_article_url

Revision ID: 0ce5fb2154d2
Revises: 5e62426e4d2f
Create Date: 2026-05-31 00:20:57.571227
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '0ce5fb2154d2'
down_revision: Union[str, None] = '5e62426e4d2f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "article_url",
        sa.Column("collected_date", sa.Date(), nullable=True),
    )
    op.create_index("ix_article_url_collected_date", "article_url", ["collected_date"])

    # 기존 행 backfill: created_at의 날짜(UTC)로 채움
    op.execute("UPDATE article_url SET collected_date = DATE(created_at) WHERE collected_date IS NULL")


def downgrade() -> None:
    op.drop_index("ix_article_url_collected_date", table_name="article_url")
    op.drop_column("article_url", "collected_date")
