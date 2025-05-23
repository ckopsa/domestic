# models.py
import uuid
from datetime import date as DateObject
from typing import Optional, Literal

from pydantic import BaseModel, Field

WIPStatus = Literal["draft", "working", "submitted", "canceled", "archived"]
BackgroundCheckStatus = Literal["pending", "in_progress", "completed", "failed", "requires_review"]


class WIPDocument(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    owner: str
    dateCreated: DateObject = Field(default_factory=DateObject.today)
    dueDate: Optional[DateObject] = None
    status: WIPStatus = "draft"

    employee_name: Optional[str] = ""
    employee_email: Optional[str] = ""
    interview_notes: Optional[str] = ""
    background_check_status: BackgroundCheckStatus = "pending"
    contract_details: Optional[str] = ""

    # Helper to convert to dict for storage if needed, Pydantic handles this mostly
    def to_dict(self):
        return self.model_dump(mode='json')  # model_dump is the newer Pydantic v2 way

    @classmethod
    def from_dict(cls, data: dict):
        # Ensure dateCreated and dueDate are proper date objects if coming from raw dict
        if isinstance(data.get("dateCreated"), str):
            data["dateCreated"] = DateObject.fromisoformat(data["dateCreated"])
        if data.get("dueDate") and isinstance(data["dueDate"], str):
            data["dueDate"] = DateObject.fromisoformat(data["dueDate"])
        return cls(**data)


# For form data that updates parts of WIPDocument
class WIPUpdateData(BaseModel):
    employee_name: Optional[str] = None
    employee_email: Optional[str] = None
    interview_notes: Optional[str] = None
    background_check_status: Optional[BackgroundCheckStatus] = None
    contract_details: Optional[str] = None
    due_date: Optional[DateObject] = None  # Allow unsetting by passing None via an empty string form field
