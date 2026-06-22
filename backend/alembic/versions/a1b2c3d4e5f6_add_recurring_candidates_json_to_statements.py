"""add recurring_candidates_json to statements

Revision ID: a1b2c3d4e5f6
Revises: 9670b8f28c89
Create Date: 2026-06-22 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "9670b8f28c89"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("statements", sa.Column("recurring_candidates_json", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("statements", "recurring_candidates_json")
