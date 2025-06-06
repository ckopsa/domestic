from enum import Enum


class WorkflowStatus(str, Enum):
    active = "active"
    completed = "completed"
    archived = "archived"
    pending = "pending"


class TaskStatus(str, Enum):
    pending = "pending"
    completed = "completed"
    in_progress = "in_progress"
