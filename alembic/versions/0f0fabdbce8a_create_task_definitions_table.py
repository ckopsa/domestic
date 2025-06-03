"""create_task_definitions_table

Revision ID: 0f0fabdbce8a
Revises: 88279b51651c
Create Date: 2024-06-05 10:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0f0fabdbce8a'
down_revision: Union[str, None] = '88279b51651c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('task_definitions',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('workflow_definition_id', sa.String(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('order', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['workflow_definition_id'], ['workflow_definitions.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_task_definitions_id'), 'task_definitions', ['id'], unique=False)
    op.create_index(op.f('ix_task_definitions_workflow_definition_id'), 'task_definitions', ['workflow_definition_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_task_definitions_workflow_definition_id'), table_name='task_definitions')
    op.drop_index(op.f('ix_task_definitions_id'), table_name='task_definitions')
    op.drop_table('task_definitions')
