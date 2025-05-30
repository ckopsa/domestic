import uuid
from sqlalchemy import Column, String, Text, Date, Enum as SQLAlchemyEnum, ForeignKey
from sqlalchemy.orm import relationship
from typing import List

from app.models.base import Base
from app.models.enums import WorkflowStatus

class WorkflowDefinition(Base):
    __tablename__ = "workflow_definitions"

    id = Column(String, primary_key=True, index=True, default=lambda: "wf_" + str(uuid.uuid4())[:8])
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True, default="")
    task_names = Column(Text, nullable=False, default="[]")  # Stored as JSON string for simplicity

    instances = relationship("WorkflowInstance", back_populates="definition")

class WorkflowInstance(Base):
    __tablename__ = "workflow_instances"

    id = Column(String, primary_key=True, index=True, default=lambda: "wf_" + str(uuid.uuid4())[:8])
    workflow_definition_id = Column(String, ForeignKey("workflow_definitions.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    user_id = Column(String, index=True, nullable=False)
    status = Column(SQLAlchemyEnum(WorkflowStatus), nullable=False, default=WorkflowStatus.active)
    created_at = Column(Date, nullable=False)

    definition = relationship("WorkflowDefinition", back_populates="instances")
    tasks = relationship("TaskInstance", back_populates="workflow_instance", order_by="TaskInstance.order")
