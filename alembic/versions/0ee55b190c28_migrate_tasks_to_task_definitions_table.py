"""migrate_tasks_to_task_definitions_table

Revision ID: 0ee55b190c28
Revises: 0f0fabdbce8a
Create Date: 2024-06-05 10:30:00 # Adjusted Create Date

"""
import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql # For JSONB

# revision identifiers, used by Alembic.
revision: str = '0ee55b190c28'
down_revision: Union[str, None] = '0f0fabdbce8a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Define table structures for use in migration
workflow_definitions_table = sa.table(
    'workflow_definitions',
    sa.column('id', sa.String),
    sa.column('task_names', postgresql.JSONB) # task_names was JSONB
)

task_definitions_table = sa.table(
    'task_definitions',
    sa.column('id', sa.String),
    sa.column('workflow_definition_id', sa.String),
    sa.column('name', sa.String),
    sa.column('order', sa.Integer)
)

def upgrade() -> None:
    connection = op.get_bind()
    # Ensure to select all columns needed, especially workflow_definitions.c.id and workflow_definitions.c.task_names
    results = connection.execute(sa.select(workflow_definitions_table.c.id, workflow_definitions_table.c.task_names)).fetchall()

    new_task_definitions = []
    for wf_id, task_names_list in results:
        if task_names_list and isinstance(task_names_list, list): # Check if task_names_list is not None and is a list
            for i, task_name in enumerate(task_names_list):
                # Ensure task_name is a string, as it's expected by the 'name' column of task_definitions
                if isinstance(task_name, str):
                    new_task_definitions.append({
                        'id': f"task_def_{str(uuid.uuid4())[:8]}",
                        'workflow_definition_id': wf_id,
                        'name': task_name,
                        'order': i
                    })
                # Optionally, add logging or error handling for tasks that are not strings

    if new_task_definitions:
        op.bulk_insert(task_definitions_table, new_task_definitions)


def downgrade() -> None:
    # This will delete all data from task_definitions.
    # This is generally acceptable as the previous migration's downgrade (0f0fabdbce8a) will drop the table.
    op.execute(task_definitions_table.delete())
