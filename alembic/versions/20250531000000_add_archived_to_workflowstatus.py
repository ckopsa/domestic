"""add archived to workflowstatus

Revision ID: add_archived_status_enum
Revises: change_task_names_to_jsonb
Create Date: 2025-05-31 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_archived_status_enum'
down_revision = 'change_task_names_to_jsonb' # From the previous migration file
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE workflowstatus ADD VALUE 'archived';")


def downgrade() -> None:
    # Removing a value from an ENUM in PostgreSQL is complex and can fail if the value is in use.
    # It often requires manual data migration or dropping and recreating the type,
    # which can be destructive or cause downtime.
    # Therefore, a simple downgrade is often not feasible or safe.
    # Consider manual steps or a more complex migration if downgrade is truly needed.
    raise NotImplementedError("Downgrade for ADD VALUE to ENUM is not implemented due to complexity and risk.")
