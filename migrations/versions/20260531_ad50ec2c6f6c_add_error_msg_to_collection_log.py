"""add_error_msg_to_collection_log

discovery 런이 예외로 중단됐을 때 이유를 collection_log 에 남기기 위해
error_msg 컬럼을 추가한다.

Revision ID: ad50ec2c6f6c
Revises: 005c8266bfd3
Create Date: 2026-05-31
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'ad50ec2c6f6c'
down_revision: Union[str, None] = '005c8266bfd3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'collection_log',
        sa.Column('error_msg', sa.String(length=500), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('collection_log', 'error_msg')
