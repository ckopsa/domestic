"""seed workflow definitions

Revision ID: seed_data
Revises: initial
Create Date: 2025-05-29 11:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'seed_data'
down_revision = 'initial'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Seed data for workflow_definitions
    op.bulk_insert(
        sa.table(
            'workflow_definitions',
            sa.column('id', sa.String),
            sa.column('name', sa.String),
            sa.column('description', sa.Text),
            sa.column('task_names', sa.Text)
        ),
        [
            {
                'id': 'def_morning_quick_start',
                'name': 'Morning Quick Start',
                'description': 'A simple routine to kick off the day.',
                'task_names': '["Make Bed", "Brush Teeth", "Get Dressed"]'
            },
            {
                'id': 'def_evening_wind_down',
                'name': 'Evening Wind Down',
                'description': "Prepare for a good night's sleep.",
                'task_names': '["Tidy Up Living Room (5 mins)", "Prepare Outfit for Tomorrow", "Read a Book (15 mins)"]'
            }
        ]
    )


def downgrade() -> None:
    # Remove seeded data
    op.execute("DELETE FROM workflow_definitions WHERE id IN ('def_morning_quick_start', 'def_evening_wind_down')")
