from sqlalchemy import Column, String, Integer, Enum as SQLAlchemyEnum, ForeignKey
from sqlalchemy.orm import relationship

from app.models.base import Base
from app.models.enums import TaskStatus

class TaskInstance(Base):
    __tablename__ = "task_instances"

    id = Column(String, primary_key=True, index=True)
    workflow_instance_id = Column(String, ForeignKey("workflow_instances.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    order = Column(Integer, nullable=False)
    status = Column(SQLAlchemyEnum(TaskStatus), nullable=False, default=TaskStatus.pending)

    workflow_instance = relationship("WorkflowInstance", back_populates="tasks")
