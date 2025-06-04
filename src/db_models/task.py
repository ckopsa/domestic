import uuid

from sqlalchemy import Column, String, Integer, Enum as SQLAlchemyEnum, ForeignKey, DateTime
from sqlalchemy.orm import relationship

from .base import Base
from .enums import TaskStatus


class TaskInstance(Base):
    __tablename__ = "task_instances"

    id = Column(String, primary_key=True, index=True, default=lambda: "task_" + str(uuid.uuid4())[:8])
    workflow_instance_id = Column(String, ForeignKey("workflow_instances.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    order = Column(Integer, nullable=False)
    status = Column(SQLAlchemyEnum(TaskStatus), nullable=False, default=TaskStatus.pending)
    due_datetime = Column(DateTime, nullable=True)

    workflow_instance = relationship("WorkflowInstance", back_populates="tasks")
