import uuid

from sqlalchemy import Column, String, Text, Date, Enum as SQLAlchemyEnum, ForeignKey
# Remove JSONB from imports if it's no longer used
from sqlalchemy.orm import relationship

from app.db_models.base import Base
# Ensure TaskDefinition is imported if it's type hinted, though SQLAlchemy relationships use strings
# from app.db_models.task_definition import TaskDefinition # May not be needed here
from app.db_models.enums import WorkflowStatus


class WorkflowDefinition(Base):
    __tablename__ = "workflow_definitions"

    id = Column(String, primary_key=True, index=True, default=lambda: "wf_" + str(uuid.uuid4())[:8])
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True, default="")
    # task_names = Column(JSONB, nullable=False, default=lambda: []) # This line is removed

    instances = relationship("WorkflowInstance", back_populates="definition")
    task_definitions = relationship("TaskDefinition", back_populates="workflow_definition", order_by="TaskDefinition.order") # This line is added


class WorkflowInstance(Base):
    __tablename__ = "workflow_instances"

    id = Column(String, primary_key=True, index=True, default=lambda: "wf_" + str(uuid.uuid4())[:8])
    workflow_definition_id = Column(String, ForeignKey("workflow_definitions.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    user_id = Column(String, index=True, nullable=False)
    status = Column(SQLAlchemyEnum(WorkflowStatus), nullable=False, default=WorkflowStatus.active)
    created_at = Column(Date, nullable=False)
    share_token = Column(String, unique=True, index=True, nullable=True)

    definition = relationship("WorkflowDefinition", back_populates="instances")
    tasks = relationship("TaskInstance", back_populates="workflow_instance", order_by="TaskInstance.order")
