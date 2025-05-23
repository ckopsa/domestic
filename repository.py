# repository.py
import uuid
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from models import WIPDocument # Assuming models.py is in the same directory or accessible

# In-memory store (moved here from main app)
_wip_documents_db: Dict[str, WIPDocument] = {}

class WIPRepository(ABC):
    @abstractmethod
    async def get_by_id(self, wip_id: str) -> Optional[WIPDocument]:
        pass

    @abstractmethod
    async def list_all(self) -> List[WIPDocument]:
        pass

    @abstractmethod
    async def create(self, wip_data: WIPDocument) -> WIPDocument:
        pass

    @abstractmethod
    async def update(self, wip_id: str, wip_doc: WIPDocument) -> Optional[WIPDocument]:
        pass

    # Delete might be useful, but current app uses status changes (cancel/archive)
    # @abstractmethod
    # async def delete(self, wip_id: str) -> bool:
    #     pass

class InMemoryWIPRepository(WIPRepository):
    async def get_by_id(self, wip_id: str) -> Optional[WIPDocument]:
        doc = _wip_documents_db.get(wip_id)
        return doc.model_copy(deep=True) if doc else None # Return a copy to prevent direct modification

    async def list_all(self) -> List[WIPDocument]:
        return [doc.model_copy(deep=True) for doc in _wip_documents_db.values()]

    async def create(self, wip_doc: WIPDocument) -> WIPDocument:
        # Ensure ID is set if not already (Pydantic model handles default factory)
        new_doc = wip_doc.model_copy(deep=True)
        _wip_documents_db[new_doc.id] = new_doc
        return new_doc.model_copy(deep=True)

    async def update(self, wip_id: str, wip_doc_update: WIPDocument) -> Optional[WIPDocument]:
        if wip_id in _wip_documents_db:
            # Pydantic model's update capabilities can be leveraged here if partial updates are complex
            # For full replacement as done before:
            _wip_documents_db[wip_id] = wip_doc_update.model_copy(deep=True)
            return _wip_documents_db[wip_id].model_copy(deep=True)
        return None