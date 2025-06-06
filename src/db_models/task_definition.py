import uuid

from sqlalchemy import Column, String, Integer, ForeignKey
from sqlalchemy.orm import relationship

from .base import Base


class TaskDefinition(Base):
    __tablename__ = "task_definitions"

    id = Column(String, primary_key=True, index=True, default=lambda: "task_def_" + str(uuid.uuid4())[:8])
    workflow_definition_id = Column(String, ForeignKey("workflow_definitions.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    order = Column(Integer, nullable=False)
    due_datetime_offset_minutes = Column(Integer, nullable=True, default=0)

    workflow_definition = relationship("WorkflowDefinition", back_populates="task_definitions")
