from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, HttpUrl, EmailStr


class TaskStatus(str, Enum):
    """
    Represents the status of an individual task within a job.
    """
    PENDING = "pending"
    WORKING = "working"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"
    REVERTED = "reverted"


class JobStatus(str, Enum):
    """
    Represents the overall status of a workflow job.
    """
    DEFINED = "defined"  # Initial state before being queued or processed
    PENDING = "pending"  # Queued or ready for execution
    WORKING = "working"  # Actively being processed
    COMPLETED = "completed"  # Successfully finished all tasks
    FAILED = "failed"  # Encountered an unrecoverable error
    CANCELED = "canceled"  # Canceled by user or system


class ContactInfo(BaseModel):
    """
    Contact information for notifications or "Calling for Help".
    """
    person: Optional[str] = Field(None, description="Name of the contact person or team.")
    email: Optional[EmailStr] = Field(None, description="Email address for notifications.")
    # Add other contact methods like SMS, voice if needed in the future


class TaskInstanceCreate(BaseModel):
    taskID: UUID = Field(default_factory=uuid4, description="Unique identifier for the task instance.")
    taskMaxTTL: Optional[int] = Field(None, description="Maximum time in seconds this task is allowed to run.")
    taskDescription: str = Field(..., description="Human-readable description of the task.")
    taskURL: HttpUrl = Field(..., description="Endpoint to to view the task details.")
    taskStartURL: HttpUrl = Field(..., description="Endpoint to call to start the task.")
    taskRollbackURL: HttpUrl = Field(..., description="Endpoint to call to revert the task.")
    taskRerunURL: HttpUrl = Field(..., description="Endpoint to call to retry the task.")
    taskCancelURL: HttpUrl = Field(..., description="Endpoint to signal task cancellation.")


class TaskInstance(TaskInstanceCreate):
    """
    Represents an instance of a task within a job.
    Corresponds to TaskDefinition/TaskInstance from the architecture.
    """
    taskStatus: TaskStatus = Field(default=TaskStatus.PENDING, description="Current status of the task.")
    taskDateCreated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    taskDateUpdated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    taskMessage: Optional[str] = Field(None, description="Details of the last execution attempt or error message.")

    class Config:
        use_enum_values = True  # Store enum values as strings


class JobInstanceCreate(BaseModel):
    """
    Represents the creation parameters for a workflow job instance.
    Corresponds to JobDefinition/JobInstanceCreate from the architecture.
    """
    tasks: List[TaskInstanceCreate] = Field(default_factory=list, description="List of task definitions for this job.")

    jobID: UUID = Field(default_factory=uuid4, description="Unique identifier for the job instance.")
    jobDescription: str = Field(..., description="Human-readable description of the job.")
    jobContact: Optional[ContactInfo] = Field(None,
                                              description="Contact information for alerts if the job requires manual intervention.")
    jobMaxTTL: Optional[int] = Field(None, description="Maximum time in seconds this job is allowed to run.")
    jobSuccessURL: Optional[HttpUrl] = Field(..., description="Endpoint to call upon successful completion of the job.")
    jobFailedURL: Optional[HttpUrl] = Field(..., description="Endpoint to call if the job fails.")


class JobInstance(BaseModel):
    """
    Represents an instance of a workflow job.
    Corresponds to JobDefinition/JobInstance from the architecture.
    """
    tasks: List[TaskInstance] = Field(default_factory=list, description="List of task instances belonging to this job.")

    jobID: UUID = Field(default_factory=uuid4, description="Unique identifier for the job instance.")
    jobDescription: str = Field(..., description="Human-readable description of the job.")
    jobContact: Optional[ContactInfo] = Field(None,
                                              description="Contact information for alerts if the job requires manual intervention.")
    jobMaxTTL: Optional[int] = Field(None, description="Maximum time in seconds this job is allowed to run.")
    jobSharedStateURL: Optional[HttpUrl] = Field(..., description="Endpoint to access the shared state for this job.")
    jobProgressURL: Optional[HttpUrl] = Field(..., description="Endpoint to access the progress information for this job.")

    jobSuccessURL: Optional[HttpUrl] = Field(..., description="Endpoint to call upon successful completion of the job.")
    jobFailedURL: Optional[HttpUrl] = Field(..., description="Endpoint to call if the job fails.")

    jobURL: HttpUrl = Field(..., description="Endpoint to view the job details.")
    jobContinueURL: HttpUrl = Field(..., description="Endpoint to call to continue the job after a pause or wait.")
    jobRestartURL: HttpUrl = Field(..., description="Endpoint to call to restart the job from the beginning.")
    jobCancelURL: HttpUrl = Field(..., description="Endpoint to signal job cancellation.")

    jobStatus: JobStatus = Field(default=JobStatus.DEFINED, description="Overall status of the job.")
    jobDateCreated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    jobDateUpdated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Config:
        use_enum_values = True  # Store enum values as strings