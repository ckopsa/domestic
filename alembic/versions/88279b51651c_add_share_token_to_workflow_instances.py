"""add_share_token_to_workflow_instances

Revision ID: 88279b51651c
Revises: add_archived_status_enum
Create Date: 2025-06-02 22:47:17.392002

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '88279b51651c'
down_revision = 'add_archived_status_enum' # This was confirmed to be correct
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('workflow_instances', sa.Column('share_token', sa.String(), nullable=True))
    op.create_index(op.f('ix_workflow_instances_share_token'), 'workflow_instances', ['share_token'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_workflow_instances_share_token'), table_name='workflow_instances')
    op.drop_column('workflow_instances', 'share_token')
