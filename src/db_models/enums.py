from enum import Enum


class WorkflowStatus(str, Enum):
    active = "active"
    completed = "completed"
    archived = "archived"


class TaskStatus(str, Enum):
    pending = "pending"
    completed = "completed"
