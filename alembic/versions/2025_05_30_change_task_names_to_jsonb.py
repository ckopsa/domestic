"""Change task_names to JSONB

Revision ID: change_task_names_to_jsonb
Revises: add_user_id
Create Date: 2025-05-30 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'change_task_names_to_jsonb'
down_revision = 'add_user_id'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Alter the column type from Text to JSONB, with a USING clause to convert existing data
    op.alter_column(
        'workflow_definitions', 
        'task_names',
        type_=postgresql.JSONB,
        postgresql_using="CASE WHEN task_names = '[]' THEN '[]'::jsonb ELSE task_names::jsonb END",
        nullable=False
    )


def downgrade() -> None:
    # Revert the column type from JSONB back to Text, converting JSONB to string
    op.alter_column(
        'workflow_definitions', 
        'task_names',
        type_=sa.Text,
        postgresql_using="task_names::text",
        nullable=False
    )
