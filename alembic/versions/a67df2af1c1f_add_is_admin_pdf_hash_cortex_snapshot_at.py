"""add_is_admin_pdf_hash_cortex_snapshot_at

Revision ID: a67df2af1c1f
Revises: e7fb905fec33
Create Date: 2026-06-21 15:44:02.999639

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a67df2af1c1f'
down_revision: Union[str, Sequence[str], None] = 'e7fb905fec33'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('analyses', sa.Column('cortex_snapshot_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('cvs', sa.Column('pdf_hash', sa.String(length=64), nullable=True))
    op.add_column('users', sa.Column('is_admin', sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    op.drop_column('users', 'is_admin')
    op.drop_column('cvs', 'pdf_hash')
    op.drop_column('analyses', 'cortex_snapshot_at')
