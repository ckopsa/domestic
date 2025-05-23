# services.py
from typing import List, Optional, Dict, Any
from datetime import date as DateObject, datetime
from models import WIPDocument, WIPStatus, WIPUpdateData
from repository import WIPRepository
import uuid # For new WIP creation

class WIPService:
    def __init__(self, repository: WIPRepository):
        self.repository = repository

    async def get_wip_by_id(self, wip_id: str) -> Optional[WIPDocument]:
        return await self.repository.get_by_id(wip_id)

    async def create_new_wip(self, title: str, owner: str, date_created: DateObject, due_date: Optional[DateObject]) -> WIPDocument:
        wip_doc = WIPDocument(
            title=title,
            owner=owner,
            dateCreated=date_created,
            dueDate=due_date
        )
        return await self.repository.create(wip_doc)

    async def update_wip_data(self, wip_id: str, update_data: WIPUpdateData) -> Optional[WIPDocument]:
        wip_doc = await self.repository.get_by_id(wip_id)
        if not wip_doc:
            return None
        if wip_doc.status in ["submitted", "canceled", "archived"]:
            # Or raise a custom business logic exception
            raise ValueError("Cannot update a submitted, canceled, or archived WIP document.")

        made_an_update = False
        update_dict = update_data.model_dump(exclude_unset=True, exclude_defaults=True) # Get only fields that were provided

        if "due_date" in update_dict: # Special handling for due_date (can be None to unset)
            if update_dict["due_date"] != wip_doc.dueDate:
                wip_doc.dueDate = update_dict["due_date"]
                made_an_update = True
            # Remove from dict to avoid Pydantic's default update behavior if it was meant to be None
            # Or ensure model_update handles Optional[Date] correctly when source is None
            # Pydantic's model_update should handle this if we pass `None` for due_date in update_dict

        # Update other fields
        for key, value in update_dict.items():
            if key == "due_date": continue # Already handled
            if hasattr(wip_doc, key) and getattr(wip_doc, key) != value:
                setattr(wip_doc, key, value)
                made_an_update = True

        if made_an_update:
            if wip_doc.status == "draft":
                wip_doc.status = "working"
            elif wip_doc.status not in ["submitted", "canceled", "archived"]: # ensure "working" if not draft and updated
                wip_doc.status = "working"
            return await self.repository.update(wip_id, wip_doc)
        return wip_doc # No actual change, return original (or updated if only status changed)

    async def submit_wip(self, wip_id: str) -> Optional[WIPDocument]:
        wip_doc = await self.repository.get_by_id(wip_id)
        if not wip_doc or wip_doc.status in ["submitted", "canceled", "archived"]:
            return None # Or raise error

        # Validation logic (can be more sophisticated)
        if not all([
            wip_doc.employee_name, wip_doc.employee_email, wip_doc.interview_notes,
            wip_doc.background_check_status == "completed", wip_doc.contract_details
        ]):
            raise ValueError("All required fields must be completed before submission.")

        wip_doc.status = "submitted"
        return await self.repository.update(wip_id, wip_doc)

    async def cancel_wip(self, wip_id: str) -> Optional[WIPDocument]:
        wip_doc = await self.repository.get_by_id(wip_id)
        if not wip_doc or wip_doc.status in ["submitted", "canceled", "archived"]:
            return None
        wip_doc.status = "canceled"
        return await self.repository.update(wip_id, wip_doc)

    async def archive_wip(self, wip_id: str) -> Optional[WIPDocument]:
        wip_doc = await self.repository.get_by_id(wip_id)
        if not wip_doc:
            return None
        if wip_doc.status not in ["submitted", "canceled"]:
            raise ValueError("Only submitted or canceled WIPs can be archived.")
        wip_doc.status = "archived"
        return await self.repository.update(wip_id, wip_doc)

    async def share_wip(self, wip_id: str, share_with_email: str) -> Optional[WIPDocument]:
        wip_doc = await self.repository.get_by_id(wip_id)
        if not wip_doc or wip_doc.status not in ["draft", "working"]:
            raise ValueError("Cannot share a non-active (draft or working) WIP document.")

        original_owner = wip_doc.owner
        wip_doc.owner = f"{share_with_email} (Shared by {original_owner})"
        return await self.repository.update(wip_id, wip_doc)

    async def get_filtered_wips(
            self,
            filter_title: Optional[str] = None,
            filter_owner: Optional[str] = None,
            filter_status: Optional[str] = None,
            due_after: Optional[DateObject] = None,
            due_before: Optional[DateObject] = None,
            filter_overdue: Optional[bool] = False
    ) -> List[WIPDocument]:
        all_wips = await self.repository.list_all()
        filtered_list = []
        today = DateObject.today()

        for wip in all_wips:
            # Status Filter
            passes_status = True
            if filter_status == "all":
                pass
            elif filter_status and filter_status.strip():
                if wip.status.lower() != filter_status.lower():
                    passes_status = False
            elif not filter_status: # Default: active
                if wip.status not in ["draft", "working"]:
                    passes_status = False
            if not passes_status:
                continue

            # Due Date Filter
            passes_due_date = True
            if filter_overdue:
                if not wip.dueDate or wip.dueDate >= today or wip.status in ["submitted", "canceled", "archived"]:
                    passes_due_date = False
            else:
                if due_after and wip.dueDate:
                    if wip.dueDate < due_after:
                        passes_due_date = False
                if due_before and wip.dueDate:
                    if wip.dueDate > due_before:
                        passes_due_date = False
            if not passes_due_date:
                continue

            # Owner Filter
            if filter_owner and filter_owner.strip().lower() not in wip.owner.lower():
                continue

            # Title Filter
            if filter_title and filter_title.strip().lower() not in wip.title.lower():
                continue

            filtered_list.append(wip)

        # Sorting
        def sort_key(x: WIPDocument):
            due = x.dueDate
            created = x.dateCreated
            # Ensure due is a comparable type (DateObject or DateObject.max)
            comparable_due = due if due is not None else DateObject.max
            return (comparable_due, created)

        return sorted(filtered_list, key=sort_key)