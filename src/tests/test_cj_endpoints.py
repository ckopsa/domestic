import pytest
from fastapi.testclient import TestClient
from typing import Optional, List, Dict, Any, Type
from datetime import datetime, timezone, timedelta
import uuid

from main import app
from models import (
    WorkflowDefinition as PDWorkflowDefinition,
    WorkflowDefinitionCreate,
    WorkflowDefinitionUpdate,
    TaskDefinitionBase,
    WorkflowInstance as PDWorkflowInstance,
    WorkflowInstanceCreate,
    WorkflowInstanceUpdate,
    TaskInstance as PDTaskInstance,
    TaskInstanceCreate,
    TaskInstanceUpdate,
    TaskInstanceBase,
    TaskStatus
)
from services import WorkflowService
from dependencies import get_workflow_service
from cj_models import CollectionJson

from pydantic import BaseModel

# --- Sample Data for Workflow Definitions ---
sample_wf_def_1_dict_orig = { # Keep original for reference if needed by other tests not being modified now
    "id": "cj-wf-def-1", "name": "Test Workflow Definition 1 (CJ)", "description": "A test workflow definition for CJ endpoints",
    "task_definitions": [
        {"name": "Task 1 for CJ def 1", "description": "First task", "order": 1, "due_datetime_offset_minutes": 60},
        {"name": "Task 2 for CJ def 1", "description": "Second task", "order": 2},
    ],
    "due_datetime": None, "created_at": datetime.now(timezone.utc), "updated_at": datetime.now(timezone.utc)
}
sample_wf_def_2_dict_orig = {
    "id": "cj-wf-def-2", "name": "Another Test Workflow (CJ)", "description": "More testing for CJ",
    "task_definitions": [{"name": "Task A for CJ def 2", "description": "Only task", "order": 1}],
    "due_datetime": None, "created_at": datetime.now(timezone.utc), "updated_at": datetime.now(timezone.utc)
}

# Payloads for Create/Update Workflow Definition
sample_wf_def_create_payload_dict = {
    "name": "New API Workflow Def",
    "description": "Created via API test (JSON)",
    "task_definitions": [
        {"name": "New Task 1", "description": "First task of new def", "order": 1, "due_datetime_offset_minutes": 30},
        {"name": "New Task 2", "description": "Second task", "order": 2}
    ],
    "due_datetime": (datetime.now(timezone.utc) + timedelta(days=10)).isoformat()
}
sample_wf_def_create_form_data = {
    "name": "New Form Workflow Def",
    "description": "Created via API test (Form)",
    "task_definitions[0][name]": "Form Task A",
    "task_definitions[0][description]": "Desc for Form Task A",
    "task_definitions[0][order]": "1", # Form data comes as strings
    "task_definitions[0][due_datetime_offset_minutes]": "120",
    "task_definitions[1][name]": "Form Task B",
    "task_definitions[1][description]": "Desc for Form Task B",
    "task_definitions[1][order]": "2",
    # "due_datetime": (datetime.now(timezone.utc) + timedelta(days=5)).isoformat() # Optional
}

sample_wf_def_update_payload_dict = {
    "name": "Updated API Workflow Def Name",
    "description": "Description updated (JSON).",
    "task_definitions": [ # Completely replaces existing task definitions
        {"name": "Updated Task X", "description": "Replacement task", "order": 1, "due_datetime_offset_minutes": 45},
    ],
    "due_datetime": None # Example: clearing the due date
}
sample_wf_def_update_form_data = {
    "name": "Updated Form Workflow Def Name",
    "description": "Description updated (Form).",
    "task_definitions[0][name]": "Updated Form Task Only",
    "task_definitions[0][description]": "This is the only task now",
    "task_definitions[0][order]": "1",
    # "due_datetime": "" # To clear it
}


# --- Sample Data for Workflow Instances (from previous tests, ensure consistency) ---
sample_wf_inst_1_task_inst_dicts = [
    {"id": "task-inst-1-1", "task_definition_id": "td-1-1", "workflow_instance_id": "cj-wf-inst-1", "name": "Task 1 for WF Inst 1", "status": TaskStatus.PENDING, "order": 1, "notes": "Notes for 1-1", "due_datetime": datetime.now(timezone.utc) + timedelta(hours=1), "created_at": datetime.now(timezone.utc), "updated_at": datetime.now(timezone.utc)},
    {"id": "task-inst-1-2", "task_definition_id": "td-1-2", "workflow_instance_id": "cj-wf-inst-1", "name": "Task 2 for WF Inst 1", "status": TaskStatus.PENDING, "order": 2, "created_at": datetime.now(timezone.utc), "updated_at": datetime.now(timezone.utc)},
]
sample_wf_inst_1_dict = {
    "id": "cj-wf-inst-1", "workflow_definition_id": sample_wf_def_1_dict_orig["id"], "name": "Instance of " + sample_wf_def_1_dict_orig["name"],
    "description": "Running instance for CJ test", "status": "pending", "user_id": "test-user-1",
    "task_instances": sample_wf_inst_1_task_inst_dicts,
    "created_at": datetime.now(timezone.utc), "updated_at": datetime.now(timezone.utc),
    "started_at": None, "completed_at": None, "due_datetime": None
}
sample_wf_inst_2_task_inst_dicts = [
    {"id": "task-inst-2-1", "task_definition_id": "td-2-1", "workflow_instance_id": "cj-wf-inst-2", "name": "Task A for WF Inst 2", "status": TaskStatus.IN_PROGRESS, "order": 1, "started_at": datetime.now(timezone.utc), "created_at": datetime.now(timezone.utc), "updated_at": datetime.now(timezone.utc)},
]
sample_wf_inst_2_dict = {
    "id": "cj-wf-inst-2", "workflow_definition_id": sample_wf_def_2_dict_orig["id"], "name": "Instance of " + sample_wf_def_2_dict_orig["name"],
    "description": "Another running instance", "status": "in_progress", "user_id": "test-user-2",
    "task_instances": sample_wf_inst_2_task_inst_dicts,
    "created_at": datetime.now(timezone.utc), "updated_at": datetime.now(timezone.utc),
    "started_at": datetime.now(timezone.utc), "completed_at": None, "due_datetime": None
}
sample_task_inst_3_dict = {
    "id": "task-inst-standalone-3", "task_definition_id": "td-generic-x", "workflow_instance_id": None,
    "name": "Standalone Task 3", "status": TaskStatus.PENDING, "order": 1, "notes": "A task not tied to a workflow instance directly in this sample set",
    "due_datetime": datetime.now(timezone.utc) + timedelta(days=5),
    "created_at": datetime.now(timezone.utc), "updated_at": datetime.now(timezone.utc)
}
sample_task_update_payload_dict = { "name": "Updated Task Name via CJ", "notes": "These are updated notes.", "status": TaskStatus.COMPLETED, "due_datetime": (datetime.now(timezone.utc) + timedelta(days=2)).isoformat() }


@pytest.fixture(scope="function")
def mock_workflow_service(db_session): # db_session not used due to mock
    # Internal store for the mock service
    MOCK_WF_DEFS_DB: Dict[str, PDWorkflowDefinition] = {}

    def _add_def_to_db(data: dict) -> PDWorkflowDefinition:
        # Helper to ensure all required fields for PDWorkflowDefinition are present
        full_data = {
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "due_datetime": None, # Default if not provided
            **data # data will override defaults
        }
        if isinstance(full_data.get("due_datetime"), str): # Convert if ISO string
            full_data["due_datetime"] = datetime.fromisoformat(full_data["due_datetime"])

        # Ensure task_definitions are TaskDefinitionBase or compatible dicts
        if "task_definitions" in full_data:
            full_data["task_definitions"] = [
                td if isinstance(td, TaskDefinitionBase) else TaskDefinitionBase(**td)
                for td in full_data["task_definitions"]
            ]
        else: # PDWorkflowDefinition requires task_definitions
            full_data["task_definitions"] = []

        instance = PDWorkflowDefinition(**full_data)
        MOCK_WF_DEFS_DB[instance.id] = instance
        return instance

    # Initialize with sample data
    _add_def_to_db(sample_wf_def_1_dict_orig)
    _add_def_to_db(sample_wf_def_2_dict_orig)

    # Workflow Instances (ensure task_instances within are PDTaskInstance models)
    wf_inst_1_tasks = [PDTaskInstance(**ti_dict) for ti_dict in sample_wf_inst_1_task_inst_dicts]
    wf_inst_1 = PDWorkflowInstance(**{**sample_wf_inst_1_dict, "task_instances": wf_inst_1_tasks})
    wf_inst_2_tasks = [PDTaskInstance(**ti_dict) for ti_dict in sample_wf_inst_2_task_inst_dicts]
    wf_inst_2 = PDWorkflowInstance(**{**sample_wf_inst_2_dict, "task_instances": wf_inst_2_tasks})

    # Task Instances
    all_task_instances_for_mock = [
        wf_inst_1.task_instances[0], wf_inst_1.task_instances[1],
        wf_inst_2.task_instances[0], PDTaskInstance(**sample_task_inst_3_dict)
    ]

    class MockWorkflowService:
        def __init__(self):
            self._called_methods = {} # Track calls with args: {"method_name": (args, kwargs)}
            self.MOCK_WF_DEFS_DB = MOCK_WF_DEFS_DB # Share the DB dict
            self.all_task_instances_for_mock = all_task_instances_for_mock


        async def list_workflow_definitions_pydantic(self, limit: int = 100, offset: int = 0, name_filter: str = None) -> List[PDWorkflowDefinition]:
            self._called_methods["list_workflow_definitions_pydantic"] = ((limit, offset, name_filter), {})
            defs = list(self.MOCK_WF_DEFS_DB.values())
            if name_filter: return [d for d in defs if name_filter.lower() in d.name.lower()][offset:offset+limit]
            return defs[offset:offset+limit]

        async def get_workflow_definition_pydantic(self, definition_id: str) -> Optional[PDWorkflowDefinition]:
            self._called_methods["get_workflow_definition_pydantic"] = ((definition_id,), {})
            return self.MOCK_WF_DEFS_DB.get(definition_id)

        async def create_workflow_definition(self, definition_data: WorkflowDefinitionCreate) -> PDWorkflowDefinition:
            self._called_methods["create_workflow_definition"] = ((definition_data,), {})
            new_id = "cj-wf-def-" + str(uuid.uuid4().hex[:6])

            # Convert TaskDefinitionBase from create_data to dicts for PDWorkflowDefinition
            task_defs_for_pd = [td.model_dump() for td in definition_data.task_definitions]

            new_def_dict = {
                "id": new_id,
                **definition_data.model_dump(exclude={"task_definitions"}), # Exclude to replace with dicts
                "task_definitions": task_defs_for_pd,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc)
            }
            created_def = PDWorkflowDefinition(**new_def_dict)
            self.MOCK_WF_DEFS_DB[new_id] = created_def
            return created_def

        async def update_workflow_definition(self, definition_id: str, definition_data: WorkflowDefinitionUpdate) -> Optional[PDWorkflowDefinition]:
            self._called_methods["update_workflow_definition"] = ((definition_id, definition_data), {})
            if definition_id not in self.MOCK_WF_DEFS_DB:
                return None

            existing_def = self.MOCK_WF_DEFS_DB[definition_id]
            update_data_dict = definition_data.model_dump(exclude_unset=True)

            # Handle task_definitions separately if present in update_data_dict
            if "task_definitions" in update_data_dict:
                # Convert TaskDefinitionBase from update_data to dicts for PDWorkflowDefinition
                update_data_dict["task_definitions"] = [td.model_dump() for td in update_data_dict["task_definitions"]]

            updated_def_data = existing_def.model_copy(update=update_data_dict) # Pydantic v2
            updated_def_data.updated_at = datetime.now(timezone.utc)

            self.MOCK_WF_DEFS_DB[definition_id] = updated_def_data
            return updated_def_data

        # ... (Workflow Instance and Task Instance methods from previous tests, ensure they use self. for consistency if they modify shared state)
        async def list_workflow_instances_pydantic(self) -> List[PDWorkflowInstance]: self._called_methods["list_workflow_instances_pydantic"] = ((),{}); return [wf_inst_1, wf_inst_2]
        async def get_workflow_instance_pydantic(self, instance_id: str) -> Optional[PDWorkflowInstance]: self._called_methods["get_workflow_instance_pydantic"] = ((instance_id,),{}); return wf_inst_1 if instance_id == wf_inst_1.id else (wf_inst_2 if instance_id == wf_inst_2.id else None)
        async def create_workflow_instance(self, instance_data: WorkflowInstanceCreate) -> PDWorkflowInstance: self._called_methods["create_workflow_instance"] = ((instance_data,),{}); new_id = "mock-wi-" + uuid.uuid4().hex[:4]; return PDWorkflowInstance(id=new_id, **instance_data.model_dump(), task_instances=[], status="pending", created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc))
        async def update_workflow_instance(self, instance_id: str, instance_data: WorkflowInstanceUpdate) -> Optional[PDWorkflowInstance]: self._called_methods["update_workflow_instance"] = ((instance_id, instance_data),{}); return PDWorkflowInstance(id=instance_id, **sample_wf_inst_1_dict, **instance_data.model_dump(exclude_unset=True), updated_at=datetime.now(timezone.utc)) if instance_id == sample_wf_inst_1_dict["id"] else None

        async def list_task_instances_pydantic(self, workflow_instance_id: Optional[str] = None, limit: int = 100, offset: int = 0) -> List[PDTaskInstance]: self._called_methods["list_task_instances_pydantic"] = ((workflow_instance_id, limit, offset),{}); return [ti for ti in self.all_task_instances_for_mock if not workflow_instance_id or ti.workflow_instance_id == workflow_instance_id][offset:offset+limit]
        async def get_task_instance_pydantic(self, task_id: str) -> Optional[PDTaskInstance]: self._called_methods["get_task_instance_pydantic"] = ((task_id,),{}); return next((ti for ti in self.all_task_instances_for_mock if ti.id == task_id), None)
        async def update_task_instance(self, task_id: str, task_data: TaskInstanceUpdate) -> Optional[PDTaskInstance]: self._called_methods["update_task_instance"] = ((task_id, task_data),{}); ti = next((ti for ti in self.all_task_instances_for_mock if ti.id == task_id), None); return PDTaskInstance(**ti.model_dump(), **task_data.model_dump(exclude_unset=True), updated_at=datetime.now(timezone.utc)) if ti else None


    return MockWorkflowService()

@pytest.fixture(scope="function")
def client(mock_workflow_service):
    app.dependency_overrides[get_workflow_service] = lambda: mock_workflow_service
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()

# Base URL for Workflow Definition CJ endpoints
WF_DEF_BASE_URL = "/cj/workflow-definitions"


# --- Existing GET tests (condensed) ---
def test_list_workflow_definitions_cj_json(client, mock_workflow_service):
    response = client.get(f"{WF_DEF_BASE_URL}/")
    assert response.status_code == 200
    # Check that initial data is there
    assert len(mock_workflow_service.MOCK_WF_DEFS_DB) >= 2
    content = response.json()
    cj_data = CollectionJson(**content)
    assert len(cj_data.collection.items) == len(mock_workflow_service.MOCK_WF_DEFS_DB)

def test_get_workflow_definition_cj_json(client, mock_workflow_service):
    def_id = sample_wf_def_1_dict_orig["id"]
    response = client.get(f"{WF_DEF_BASE_URL}/{def_id}/")
    assert response.status_code == 200
    content = response.json()
    cj_data = CollectionJson(**content)
    assert cj_data.collection.items[0].data[0].value == sample_wf_def_1_dict_orig["name"]

def test_get_workflow_definition_create_form_cj_json(client): # Renamed
    response = client.get(f"{WF_DEF_BASE_URL}/form/")
    assert response.status_code == 200
    content = response.json()
    cj_data = CollectionJson(**content)
    assert cj_data.collection.template is not None
    # Check for a field from WorkflowDefinitionCreate
    assert any(td.name == "name" for td in cj_data.collection.template.data)
    assert not any(td.name == "id" for td in cj_data.collection.template.data) # id not in create

def test_get_workflow_definition_edit_form_cj_json(client): # Renamed
    def_id = sample_wf_def_1_dict_orig["id"]
    response = client.get(f"{WF_DEF_BASE_URL}/{def_id}/form/")
    assert response.status_code == 200
    content = response.json()
    cj_data = CollectionJson(**content)
    assert cj_data.collection.template is not None
    # Check that a field is pre-filled
    name_field = next(td for td in cj_data.collection.template.data if td.name == "name")
    assert name_field.value == sample_wf_def_1_dict_orig["name"]


# --- Tests for PUT Endpoints ---

def test_create_workflow_definition_cj_json(client, mock_workflow_service):
    response = client.put(f"{WF_DEF_BASE_URL}/form/", json=sample_wf_def_create_payload_dict)
    assert response.status_code == 201

    args, _ = mock_workflow_service._called_methods["create_workflow_definition"]
    created_data_arg: WorkflowDefinitionCreate = args[0]
    assert created_data_arg.name == sample_wf_def_create_payload_dict["name"]
    assert len(created_data_arg.task_definitions) == len(sample_wf_def_create_payload_dict["task_definitions"])
    assert created_data_arg.task_definitions[0].name == sample_wf_def_create_payload_dict["task_definitions"][0]["name"]

    content = response.json()
    cj_data = CollectionJson(**content)
    assert len(cj_data.collection.items) == 1
    item = cj_data.collection.items[0]
    item_name = next(d.value for d in item.data if d.name == "name")
    assert item_name == sample_wf_def_create_payload_dict["name"]
    assert item.href.endswith(f"{WF_DEF_BASE_URL}/{item.data[0].value if item.data[0].name == 'id' else [d.value for d in item.data if d.name=='id'][0]}/") # Check href of created item

def test_create_workflow_definition_cj_form_urlencoded(client, mock_workflow_service):
    response = client.put(
        f"{WF_DEF_BASE_URL}/form/",
        data=sample_wf_def_create_form_data,
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    assert response.status_code == 303 # Redirect

    args, _ = mock_workflow_service._called_methods["create_workflow_definition"]
    created_data_arg: WorkflowDefinitionCreate = args[0]
    assert created_data_arg.name == sample_wf_def_create_form_data["name"]
    assert len(created_data_arg.task_definitions) == 2 # Based on sample_wf_def_create_form_data
    assert created_data_arg.task_definitions[0].name == sample_wf_def_create_form_data["task_definitions[0][name]"]
    assert created_data_arg.task_definitions[0].order == int(sample_wf_def_create_form_data["task_definitions[0][order]"])

    # Find the ID of the created definition from the mock service's internal DB
    # This is a bit indirect; relies on the mock service correctly storing the item.
    created_def_in_mock = None
    for def_id, wf_def in mock_workflow_service.MOCK_WF_DEFS_DB.items():
        if wf_def.name == sample_wf_def_create_form_data["name"]:
            created_def_in_mock = wf_def
            break
    assert created_def_in_mock is not None
    assert response.headers["Location"].endswith(f"{WF_DEF_BASE_URL}/{created_def_in_mock.id}/")


def test_update_workflow_definition_cj_json(client, mock_workflow_service):
    def_id_to_update = sample_wf_def_1_dict_orig["id"]
    response = client.put(f"{WF_DEF_BASE_URL}/{def_id_to_update}/form/", json=sample_wf_def_update_payload_dict)
    assert response.status_code == 200

    args, _ = mock_workflow_service._called_methods["update_workflow_definition"]
    called_id_arg, updated_data_arg = args[0], args[1]
    assert called_id_arg == def_id_to_update
    assert updated_data_arg.name == sample_wf_def_update_payload_dict["name"]
    assert len(updated_data_arg.task_definitions) == len(sample_wf_def_update_payload_dict["task_definitions"])

    content = response.json()
    cj_data = CollectionJson(**content)
    item = cj_data.collection.items[0]
    item_name = next(d.value for d in item.data if d.name == "name")
    assert item_name == sample_wf_def_update_payload_dict["name"]
    assert item.href.endswith(f"{WF_DEF_BASE_URL}/{def_id_to_update}/")

def test_update_workflow_definition_cj_form_urlencoded(client, mock_workflow_service):
    def_id_to_update = sample_wf_def_2_dict_orig["id"] # Use the second definition
    response = client.put(
        f"{WF_DEF_BASE_URL}/{def_id_to_update}/form/",
        data=sample_wf_def_update_form_data,
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    assert response.status_code == 303

    args, _ = mock_workflow_service._called_methods["update_workflow_definition"]
    called_id_arg, updated_data_arg = args[0], args[1]
    assert called_id_arg == def_id_to_update
    assert updated_data_arg.name == sample_wf_def_update_form_data["name"]
    assert len(updated_data_arg.task_definitions) == 1 # Based on sample_wf_def_update_form_data
    assert updated_data_arg.task_definitions[0].name == sample_wf_def_update_form_data["task_definitions[0][name]"]

    assert response.headers["Location"].endswith(f"{WF_DEF_BASE_URL}/{def_id_to_update}/")

def test_update_workflow_definition_not_found_cj_json(client, mock_workflow_service):
    non_existent_id = "wf-def-non-existent"
    response = client.put(f"{WF_DEF_BASE_URL}/{non_existent_id}/form/", json=sample_wf_def_update_payload_dict)
    assert response.status_code == 404

    content = response.json()
    cj_data = CollectionJson(**content)
    assert cj_data.collection.error is not None
    assert cj_data.collection.error.code == 404
    assert "not found" in cj_data.collection.error.message.lower()

# Placeholder for other existing tests (Workflow Instance, Task Instance)
# These should ideally be in separate files if they grow too large.
WF_INST_BASE_URL = "/cj/workflow-instances"
TASK_INST_BASE_URL = "/cj/task-instances"
def test_list_workflow_instances_cj_json(client, mock_workflow_service): response = client.get(f"{WF_INST_BASE_URL}/"); assert response.status_code == 200
def test_list_task_instances_cj_json(client, mock_workflow_service): response = client.get(f"{TASK_INST_BASE_URL}/"); assert response.status_code == 200
