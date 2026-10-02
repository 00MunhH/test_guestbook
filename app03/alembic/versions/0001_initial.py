"""initial schema (모델 메타데이터 기준 전체 생성)

Revision ID: 0001_initial
Revises:
Create Date: 2026-10-02

이 초기 리비전은 현재 ORM 모델 전체를 그대로 생성한다.
이후 스키마 변경부터는 `alembic revision --autogenerate -m "..."`로 정식 리비전을 만든다.
"""
from typing import Sequence, Union

from alembic import op  # noqa: F401

from app.database import Base
from app import models  # noqa: F401

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
