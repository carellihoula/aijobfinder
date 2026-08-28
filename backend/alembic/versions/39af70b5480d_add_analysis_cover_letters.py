"""add_analysis_cover_letters

Revision ID: 39af70b5480d
Revises: 35561bd65001
Create Date: 2026-08-27 22:50:09.277786

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '39af70b5480d'
down_revision: Union[str, Sequence[str], None] = '35561bd65001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'analysis_cover_letters',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('analysis_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('job_index', sa.Integer(), nullable=False),
        sa.Column('content', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['analysis_id'], ['analyses.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('analysis_id', 'job_index', name='uq_analysis_cover_letter'),
    )
    op.create_index(op.f('ix_analysis_cover_letters_analysis_id'), 'analysis_cover_letters', ['analysis_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_analysis_cover_letters_analysis_id'), table_name='analysis_cover_letters')
    op.drop_table('analysis_cover_letters')
