"""add_cover_letter_status_and_description_to_applications

Revision ID: dbe12f03202f
Revises: af4545b633b6
Create Date: 2026-08-06 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'dbe12f03202f'
down_revision: Union[str, Sequence[str], None] = 'af4545b633b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('applications', sa.Column('description', sa.Text(), nullable=True))
    op.add_column('applications', sa.Column('cover_letter_status', sa.String(), nullable=False, server_default='pending'))
    op.add_column('applications', sa.Column('cover_letter_content', postgresql.JSON(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('applications', 'cover_letter_content')
    op.drop_column('applications', 'cover_letter_status')
    op.drop_column('applications', 'description')
