from enum import Enum

class WorkflowStatus(str, Enum):
    active = "active"
    completed = "completed"
    ARCHIVED = "archived"

class TaskStatus(str, Enum):
    pending = "pending"
    completed = "completed"
