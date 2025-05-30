"""add user_id to workflow_instances

Revision ID: add_user_id
Revises: seed_data
Create Date: 2025-05-30 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_user_id'
down_revision = 'seed_data'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add user_id column to workflow_instances
    op.add_column('workflow_instances', sa.Column('user_id', sa.String(), nullable=False, index=True, server_default='anonymous'))


def downgrade() -> None:
    # Remove user_id column from workflow_instances
    op.drop_column('workflow_instances', 'user_id')
