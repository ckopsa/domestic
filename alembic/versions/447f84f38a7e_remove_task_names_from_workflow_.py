"""remove_task_names_from_workflow_definitions

Revision ID: 447f84f38a7e
Revises: 0ee55b190c28
Create Date: 2024-06-05 11:00:00 # Adjusted Create Date

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '447f84f38a7e'
down_revision: Union[str, None] = '0ee55b190c28'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column('workflow_definitions', 'task_names')


def downgrade() -> None:
    # Re-adds the 'task_names' column, attempting to match original schema:
    # Original was: Column(JSONB, nullable=False, default=lambda: [])
    # The `default=lambda: []` is a client-side default.
    # For a non-nullable column, a server_default is appropriate.
    op.add_column('workflow_definitions',
                  sa.Column('task_names',
                            postgresql.JSONB(),
                            nullable=False,
                            server_default=sa.text("'[]'::jsonb")))
