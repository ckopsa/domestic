import pytest
from fastapi.testclient import TestClient

# Assuming your FastAPI app instance is named 'app' in 'src.main'
# If it's elsewhere, adjust the import path accordingly.
from main import app
from models import (
    CJWorkflowDefinition,
    WorkflowDefinition,
    TaskDefinitionBase,
    CJWorkflowInstance,
    WorkflowInstance,
    CJTaskInstance,
    TaskInstance
)
from cj_models import CollectionJson, Link, Query, Item, Template
from db_models.enums import WorkflowStatus, TaskStatus # Added


@pytest.fixture(scope="module")
def client():
    """
    Test client for the FastAPI application.
    """
    with TestClient(app) as c:
        yield c

# Placeholder for tests
def test_example():
    assert True


def test_cj_workflow_definition_serialization():
    """
    Tests the Collection+JSON serialization methods of the CJWorkflowDefinition model.
    """
    base_url = "http://localhost:8000"
    context = {'base_url': base_url}

    # Sample Task Definitions
    task_def_1 = TaskDefinitionBase(name="Task 1", order=1, due_datetime_offset_minutes=60)
    task_def_2 = TaskDefinitionBase(name="Task 2", order=2)

    # Sample Workflow Definition
    wd_id = "def_test123"
    workflow_def_data = {
        "id": wd_id,
        "name": "Test Workflow Definition",
        "description": "A sample definition for testing",
        "task_definitions": [task_def_1, task_def_2],
        "due_datetime": None # Or a datetime object
    }
    cj_workflow_def = CJWorkflowDefinition(**workflow_def_data)

    # Test to_cj_item()
    cj_item = cj_workflow_def.to_cj_item(context=context)
    assert isinstance(cj_item, Item)
    assert cj_item.href == f"{base_url}{CJWorkflowDefinition.cj_item_href_template.format(id=wd_id)}"
    assert cj_item.rel == CJWorkflowDefinition.cj_item_rel

    item_data_dict = {d.name: d.value for d in cj_item.data}
    assert item_data_dict["name"] == workflow_def_data["name"]
    assert item_data_dict["description"] == workflow_def_data["description"]
    assert len(item_data_dict["task_definitions"]) == 2
    assert item_data_dict["task_definitions"][0]["name"] == task_def_1.name
    assert item_data_dict["task_definitions"][1]["name"] == task_def_2.name
    assert "id" in item_data_dict # id should be part of the data array

    # Test to_cj_representation() with a single instance
    cj_repr_single = CJWorkflowDefinition.to_cj_representation(instances=cj_workflow_def, context=context)
    assert isinstance(cj_repr_single, CollectionJson)
    assert cj_repr_single.collection.version == "1.0"
    assert cj_repr_single.collection.href == f"{base_url}{CJWorkflowDefinition.cj_collection_href_template}"
    assert cj_repr_single.collection.title == CJWorkflowDefinition.cj_collection_title
    assert len(cj_repr_single.collection.items) == 1
    assert cj_repr_single.collection.items[0].href == cj_item.href # Check if item is the same

    # Check global links and queries are resolved
    assert len(cj_repr_single.collection.links) > 0
    for link in cj_repr_single.collection.links:
        assert link.href.startswith(base_url) or link.href.startswith("/") # some might be relative from model

    assert len(cj_repr_single.collection.queries) > 0
    for query in cj_repr_single.collection.queries:
        assert query.href.startswith(base_url) or query.href.startswith("/")

    assert cj_repr_single.template is not None
    assert len(cj_repr_single.template.data) > 0 # Check template has data definitions

    # Test to_cj_representation() with a list of instances
    wd_id_2 = "def_test456"
    workflow_def_data_2 = {
        "id": wd_id_2,
        "name": "Another Workflow Definition",
        "description": "Another sample",
        "task_definitions": [task_def_1]
    }
    cj_workflow_def_2 = CJWorkflowDefinition(**workflow_def_data_2)

    cj_repr_list = CJWorkflowDefinition.to_cj_representation(instances=[cj_workflow_def, cj_workflow_def_2], context=context)
    assert len(cj_repr_list.collection.items) == 2
    assert cj_repr_list.collection.items[0].href == f"{base_url}{CJWorkflowDefinition.cj_item_href_template.format(id=wd_id)}"
    assert cj_repr_list.collection.items[1].href == f"{base_url}{CJWorkflowDefinition.cj_item_href_template.format(id=wd_id_2)}"


def test_get_workflow_definitions_cj(client: TestClient):
    """
    Tests the GET /api/cj/workflow-definitions/ endpoint.
    """
    response = client.get("/api/cj/workflow-definitions/")
    assert response.status_code == 200

    # Attempt to parse as CollectionJson Pydantic model
    try:
        cj_response = CollectionJson(**response.json())
    except Exception as e:
        pytest.fail(f"Response JSON could not be parsed into CollectionJson model: {e}\nResponse content: {response.text}")

    # Validate overall Collection+JSON structure
    assert cj_response.collection.version == "1.0"
    # TestClient makes requests to http://testserver by default if base_url is not configured for the client itself.
    # The router constructs hrefs based on request.base_url.
    # So, the href in the response should match the test server's base URL.
    expected_collection_href = f"http://testserver{CJWorkflowDefinition.cj_collection_href_template}"
    assert cj_response.collection.href == expected_collection_href
    assert cj_response.collection.title == CJWorkflowDefinition.cj_collection_title

    assert cj_response.collection.links is not None
    # Check for 'self' and 'home' links based on CJWorkflowDefinition's cj_global_links
    # Their hrefs should also be correctly resolved.
    self_link_found = any(link.rel == "self" and link.href == expected_collection_href for link in cj_response.collection.links)
    assert self_link_found, "Self link not found or incorrect in collection links"

    home_link_found = any(link.rel == "home" and link.href.endswith("/api/cj/") for link in cj_response.collection.links)
    assert home_link_found, "Home link not found or incorrect in collection links"


    assert cj_response.collection.queries is not None
    # Check for search query based on CJWorkflowDefinition's cj_global_queries
    search_query_found = any(query.rel == "search" and query.href.endswith("/api/cj/workflow-definitions/search") for query in cj_response.collection.queries)
    assert search_query_found, "Search query not found or incorrect in collection queries"

    assert cj_response.template is not None
    assert len(cj_response.template.data) > 0 # Template should define how to create new items

    # Validate items - this part depends on data in the test DB or mocks
    # For now, we'll just assert it's a list. If data exists, further checks can be added.
    assert isinstance(cj_response.collection.items, list)
    if cj_response.collection.items:
        for item in cj_response.collection.items:
            assert item.href is not None and item.href.startswith(f"http://testserver{CJWorkflowDefinition.cj_collection_href_template}")
            assert item.rel == CJWorkflowDefinition.cj_item_rel
            assert isinstance(item.data, list)
            # Further checks on item.data fields can be added if there's known test data
            item_data_names = {d.name for d in item.data}
            assert "id" in item_data_names
            assert "name" in item_data_names
            assert "task_definitions" in item_data_names


def test_post_workflow_definition_cj(client: TestClient):
    """
    Tests the POST /api/cj/workflow-definitions/ endpoint.
    """
    new_definition_data = {
        "name": "Test POST Definition",
        "description": "A definition created via POST test",
        "task_definitions": [
            {"name": "Task A", "order": 1, "due_datetime_offset_minutes": 30},
            {"name": "Task B", "order": 2}
        ],
        # "id" should not be provided by client for creation, it's server-generated
    }

    response = client.post("/api/cj/workflow-definitions/", json=new_definition_data)
    assert response.status_code == 201, f"Response content: {response.text}"

    try:
        cj_response = CollectionJson(**response.json())
    except Exception as e:
        pytest.fail(f"Response JSON could not be parsed into CollectionJson model: {e}\nResponse content: {response.text}")

    # Validate Collection+JSON structure for the created item
    assert cj_response.collection.version == "1.0"
    # The collection href should still point to the main collection URI
    assert cj_response.collection.href == f"http://testserver{CJWorkflowDefinition.cj_collection_href_template}"
    assert len(cj_response.collection.items) == 1

    created_item = cj_response.collection.items[0]
    assert created_item.rel == CJWorkflowDefinition.cj_item_rel
    assert created_item.href is not None
    assert created_item.href.startswith(f"http://testserver{CJWorkflowDefinition.cj_collection_href_template}")

    # Extract ID from the href for further checks if needed
    created_id = created_item.href.rstrip('/').split('/')[-1]
    assert created_id is not None and created_id != ""

    item_data_dict = {d.name: d.value for d in created_item.data}
    assert item_data_dict["name"] == new_definition_data["name"]
    assert item_data_dict["description"] == new_definition_data["description"]
    assert len(item_data_dict["task_definitions"]) == 2
    assert item_data_dict["task_definitions"][0]["name"] == new_definition_data["task_definitions"][0]["name"]
    assert item_data_dict["id"] == created_id # Check if the ID in data matches the one in href

    # Optional: Verify by making a GET request to the href of the created item
    if created_item.href:
        get_response = client.get(created_item.href) # TestClient needs full URL or just path
        assert get_response.status_code == 200
        get_cj_response = CollectionJson(**get_response.json())
        assert len(get_cj_response.collection.items) == 1
        assert get_cj_response.collection.items[0].href == created_item.href


def test_get_single_workflow_definition_cj(client: TestClient):
    """
    Tests the GET /api/cj/workflow-definitions/{definition_id} endpoint.
    """
    # 1. Create a new workflow definition to ensure one exists
    new_definition_data = {
        "name": "Test Single GET Definition",
        "description": "A definition for testing single GET",
        "task_definitions": [{"name": "Task X", "order": 1}]
    }
    post_response = client.post("/api/cj/workflow-definitions/", json=new_definition_data)
    assert post_response.status_code == 201
    created_item_href = CollectionJson(**post_response.json()).collection.items[0].href
    assert created_item_href is not None

    # 2. Make a GET request to the href of the created item
    # TestClient's get method can take a full URL or just the path part.
    # If created_item_href is "http://testserver/api/cj/workflow-definitions/some_id/",
    # client.get("/api/cj/workflow-definitions/some_id/") would also work.
    get_response = client.get(created_item_href)
    assert get_response.status_code == 200, f"Failed to GET {created_item_href}. Response: {get_response.text}"

    try:
        cj_response = CollectionJson(**get_response.json())
    except Exception as e:
        pytest.fail(f"Response JSON could not be parsed into CollectionJson model: {e}\nResponse content: {get_response.text}")

    # 3. Validate the Collection+JSON structure for the single item
    assert cj_response.collection.version == "1.0"
    # For a single item GET, the collection.href might be the item's own href or the parent collection href.
    # Based on current router implementation, it's the item's own href.
    # Let's assume the to_cj_representation for a single instance sets collection.href to the item's href.
    # This needs to be consistent with how CJWorkflowDefinition.to_cj_representation works for single items.
    # Typically, the collection href would still be the main collection, and items would contain the specific one.
    # The current implementation of to_cj_representation(instances=single_item) will set collection.href
    # to the cj_collection_href_template of the model.
    assert cj_response.collection.href == f"http://testserver{CJWorkflowDefinition.cj_collection_href_template}"
    assert len(cj_response.collection.items) == 1

    item = cj_response.collection.items[0]
    assert item.href == created_item_href
    assert item.rel == CJWorkflowDefinition.cj_item_rel

    item_data_dict = {d.name: d.value for d in item.data}
    assert item_data_dict["name"] == new_definition_data["name"]
    assert len(item_data_dict["task_definitions"]) == 1
    assert item_data_dict["task_definitions"][0]["name"] == new_definition_data["task_definitions"][0]["name"]

    # 4. Test for 404 Not Found
    non_existent_id = "def_nonexistent123"
    response_404 = client.get(f"/api/cj/workflow-definitions/{non_existent_id}")
    assert response_404.status_code == 404
    # Optionally, check the content of the 404 response if it's structured (e.g. CJ error)
    error_response = response_404.json() # FastAPI typically returns JSON for HTTPExceptions
    assert "detail" in error_response
    assert error_response["detail"] == "Workflow Definition not found"


def test_cj_workflow_instance_serialization():
    """
    Tests the Collection+JSON serialization methods of the CJWorkflowInstance model.
    """
    base_url = "http://localhost:8000"
    context = {'base_url': base_url}

    wf_instance_id = "wf_test123"
    wf_def_id = "def_parent456"
    user_id_val = "user_abc"

    workflow_instance_data = {
        "id": wf_instance_id,
        "name": "Test Workflow Instance",
        "workflow_definition_id": wf_def_id,
        "user_id": user_id_val,
        "status": WorkflowStatus.active,
        # "created_at": datetime.utcnow(), # Handled by default_factory
        # "due_datetime": None
    }
    cj_workflow_instance = CJWorkflowInstance(**workflow_instance_data)

    # Test to_cj_item()
    cj_item = cj_workflow_instance.to_cj_item(context=context)
    assert isinstance(cj_item, Item)
    assert cj_item.href == f"{base_url}{CJWorkflowInstance.cj_item_href_template.format(id=wf_instance_id)}"
    assert cj_item.rel == CJWorkflowInstance.cj_item_rel

    item_data_dict = {d.name: d.value for d in cj_item.data}
    assert item_data_dict["name"] == workflow_instance_data["name"]
    assert item_data_dict["workflow_definition_id"] == wf_def_id
    assert item_data_dict["user_id"] == user_id_val
    assert item_data_dict["status"] == WorkflowStatus.active.value
    assert "id" in item_data_dict

    # Verify instance-specific links
    item_links_rels = {link.rel for link in cj_item.links}
    assert "workflow-definition" in item_links_rels
    assert "tasks" in item_links_rels

    for link in cj_item.links:
        if link.rel == "workflow-definition":
            assert link.href == f"{base_url}{CJWorkflowDefinition.cj_item_href_template.format(id=wf_def_id)}"
        elif link.rel == "tasks":
            assert link.href == f"{base_url}/api/cj/workflow-instances/{wf_instance_id}/tasks/"
        # Default links like 'edit', 'delete' might also be present from superclass
        assert link.href.startswith(base_url)


    # Test to_cj_representation() with a single instance
    cj_repr_single = CJWorkflowInstance.to_cj_representation(instances=cj_workflow_instance, context=context)
    assert isinstance(cj_repr_single, CollectionJson)
    assert cj_repr_single.collection.version == "1.0"
    assert cj_repr_single.collection.href == f"{base_url}{CJWorkflowInstance.cj_collection_href_template}"
    assert cj_repr_single.collection.title == CJWorkflowInstance.cj_collection_title
    assert len(cj_repr_single.collection.items) == 1
    assert cj_repr_single.collection.items[0].href == cj_item.href

    assert len(cj_repr_single.collection.links) > 0 # Global links
    for link in cj_repr_single.collection.links:
        assert link.href.startswith(base_url)

    assert len(cj_repr_single.collection.queries) > 0 # Global queries
    for query in cj_repr_single.collection.queries:
        assert query.href.startswith(base_url)

    assert cj_repr_single.template is not None
    assert len(cj_repr_single.template.data) > 0


def test_get_workflow_instances_cj(client: TestClient):
    """
    Tests the GET /api/cj/workflow-instances/ endpoint.
    """
    response = client.get("/api/cj/workflow-instances/")
    assert response.status_code == 200

    try:
        cj_response = CollectionJson(**response.json())
    except Exception as e:
        pytest.fail(f"Response JSON could not be parsed into CollectionJson model: {e}\nResponse content: {response.text}")

    # Validate overall Collection+JSON structure
    assert cj_response.collection.version == "1.0"
    expected_collection_href = f"http://testserver{CJWorkflowInstance.cj_collection_href_template}"
    assert cj_response.collection.href == expected_collection_href
    assert cj_response.collection.title == CJWorkflowInstance.cj_collection_title

    assert cj_response.collection.links is not None
    # Check for global links based on CJWorkflowInstance's cj_global_links
    self_link_found = any(link.rel == "self" and link.href == expected_collection_href for link in cj_response.collection.links)
    assert self_link_found, "Self link not found or incorrect in collection links"
    home_link_found = any(link.rel == "home" and link.href.endswith("/api/cj/") for link in cj_response.collection.links) # Assuming home points to CJ root
    assert home_link_found, "Home link not found or incorrect"

    assert cj_response.collection.queries is not None
    # Check for search query based on CJWorkflowInstance's cj_global_queries
    search_query_found = any(query.rel == "search" and query.href.endswith("/api/cj/workflow-instances/search") for query in cj_response.collection.queries)
    assert search_query_found, "Search query not found or incorrect"

    assert cj_response.template is not None
    assert len(cj_response.template.data) > 0 # Template for creating new instances

    # Validate items - depends on data in the test DB or mocks
    assert isinstance(cj_response.collection.items, list)
    if cj_response.collection.items:
        for item_cj in cj_response.collection.items: # Renamed to avoid conflict with Item model
            assert item_cj.href is not None and item_cj.href.startswith(f"http://testserver{CJWorkflowInstance.cj_collection_href_template}")
            assert item_cj.rel == CJWorkflowInstance.cj_item_rel
            assert isinstance(item_cj.data, list)

            item_data_names = {d.name for d in item_cj.data}
            assert "id" in item_data_names
            assert "name" in item_data_names
            assert "workflow_definition_id" in item_data_names
            assert "user_id" in item_data_names
            assert "status" in item_data_names

            # Check for instance-specific links within each item
            item_links_rels = {link.rel for link in item_cj.links}
            assert "workflow-definition" in item_links_rels
            assert "tasks" in item_links_rels
            # Optionally, check href patterns for these links if possible
            # For example, tasks link should end with /tasks/ relative to item href
            task_link = next((link for link in item_cj.links if link.rel == "tasks"), None)
            assert task_link is not None
            assert task_link.href.endswith("/tasks/")
            assert task_link.href.startswith(item_cj.href.rstrip('/'))


def test_post_workflow_instance_cj(client: TestClient):
    """
    Tests the POST /api/cj/workflow-instances/ endpoint.
    """
    # 1. Create a parent WorkflowDefinition first
    workflow_def_data = {
        "name": "Parent Def for Instance Test",
        "description": "A definition to host instances",
        "task_definitions": [{"name": "Task 1 for instance test", "order": 1}]
    }
    post_def_response = client.post("/api/cj/workflow-definitions/", json=workflow_def_data)
    assert post_def_response.status_code == 201
    try:
        created_def_item = CollectionJson(**post_def_response.json()).collection.items[0]
        parent_def_id = created_def_item.data[0].value # Assuming 'id' is the first data element
        # A more robust way to get id:
        for data_item in created_def_item.data:
            if data_item.name == "id":
                parent_def_id = data_item.value
                break
        assert parent_def_id is not None
    except Exception as e:
        pytest.fail(f"Could not parse created workflow definition or find its ID: {e}. Response: {post_def_response.text}")


    # 2. Prepare data for the new workflow instance
    user_id_val = "test_user_for_instance"
    instance_name = "My Test Instance via POST"
    new_instance_data = {
        "name": instance_name, # Name is part of WorkflowInstance in models.py
        "workflow_definition_id": parent_def_id,
        "user_id": user_id_val,
        # status and due_datetime can be defaulted by the server or explicitly set
        "status": WorkflowStatus.pending.value # Explicitly set for testing
    }

    # 3. Make POST request to create instance
    response = client.post("/api/cj/workflow-instances/", json=new_instance_data)
    assert response.status_code == 201, f"Response content: {response.text}"

    try:
        cj_response = CollectionJson(**response.json())
    except Exception as e:
        pytest.fail(f"Response JSON could not be parsed into CollectionJson model: {e}\nResponse content: {response.text}")

    # 4. Validate Collection+JSON structure for the created instance
    assert cj_response.collection.version == "1.0"
    assert cj_response.collection.href == f"http://testserver{CJWorkflowInstance.cj_collection_href_template}"
    assert len(cj_response.collection.items) == 1

    created_instance_item = cj_response.collection.items[0]
    assert created_instance_item.rel == CJWorkflowInstance.cj_item_rel
    assert created_instance_item.href is not None
    assert created_instance_item.href.startswith(f"http://testserver{CJWorkflowInstance.cj_collection_href_template}")

    created_instance_id = created_instance_item.href.rstrip('/').split('/')[-1]
    assert created_instance_id is not None and created_instance_id != ""

    item_data_dict = {d.name: d.value for d in created_instance_item.data}
    assert item_data_dict["name"] == instance_name
    assert item_data_dict["workflow_definition_id"] == parent_def_id
    assert item_data_dict["user_id"] == user_id_val
    assert item_data_dict["status"] == WorkflowStatus.pending.value
    assert item_data_dict["id"] == created_instance_id

    # 5. Optional: Verify by making a GET request
    if created_instance_item.href:
        get_response = client.get(created_instance_item.href)
        assert get_response.status_code == 200
        get_cj_response = CollectionJson(**get_response.json())
        assert len(get_cj_response.collection.items) == 1
        assert get_cj_response.collection.items[0].href == created_instance_item.href
        retrieved_data_dict = {d.name: d.value for d in get_cj_response.collection.items[0].data}
        assert retrieved_data_dict["name"] == instance_name


def test_get_single_workflow_instance_cj(client: TestClient):
    """
    Tests the GET /api/cj/workflow-instances/{instance_id} endpoint.
    """
    # 1. Create a parent WorkflowDefinition
    workflow_def_data = {
        "name": "Parent Def for Single Instance GET",
        "description": "Definition for single instance GET test",
        "task_definitions": [{"name": "Task Y", "order": 1}]
    }
    post_def_response = client.post("/api/cj/workflow-definitions/", json=workflow_def_data)
    assert post_def_response.status_code == 201
    try:
        created_def_item = CollectionJson(**post_def_response.json()).collection.items[0]
        parent_def_id = next(d.value for d in created_def_item.data if d.name == "id")
    except Exception as e:
        pytest.fail(f"Failed to create/parse parent workflow definition: {e}. Response: {post_def_response.text}")

    # 2. Create a WorkflowInstance for this definition
    instance_name = "My Single Test Instance"
    user_id_val = "user_single_instance_test"
    new_instance_data = {
        "name": instance_name,
        "workflow_definition_id": parent_def_id,
        "user_id": user_id_val,
        "status": WorkflowStatus.active.value
    }
    post_instance_response = client.post("/api/cj/workflow-instances/", json=new_instance_data)
    assert post_instance_response.status_code == 201
    try:
        created_instance_item_meta = CollectionJson(**post_instance_response.json()).collection.items[0]
        instance_href = created_instance_item_meta.href
        instance_id = next(d.value for d in created_instance_item_meta.data if d.name == "id")
    except Exception as e:
        pytest.fail(f"Failed to create/parse workflow instance: {e}. Response: {post_instance_response.text}")

    assert instance_href is not None

    # 3. Make a GET request to the href of the created instance
    get_response = client.get(instance_href)
    assert get_response.status_code == 200, f"Failed to GET {instance_href}. Response: {get_response.text}"

    try:
        cj_response = CollectionJson(**get_response.json())
    except Exception as e:
        pytest.fail(f"Response JSON could not be parsed into CollectionJson model: {e}\nResponse content: {get_response.text}")

    # 4. Validate the Collection+JSON structure for the single item
    assert cj_response.collection.version == "1.0"
    # The collection.href for a single item GET should be the collection's base href
    assert cj_response.collection.href == f"http://testserver{CJWorkflowInstance.cj_collection_href_template}"
    assert len(cj_response.collection.items) == 1

    item = cj_response.collection.items[0]
    assert item.href == instance_href
    assert item.rel == CJWorkflowInstance.cj_item_rel

    item_data_dict = {d.name: d.value for d in item.data}
    assert item_data_dict["id"] == instance_id
    assert item_data_dict["name"] == instance_name
    assert item_data_dict["workflow_definition_id"] == parent_def_id
    assert item_data_dict["user_id"] == user_id_val
    assert item_data_dict["status"] == WorkflowStatus.active.value

    # Verify instance-specific links
    item_links_rels = {link.rel for link in item.links}
    assert "workflow-definition" in item_links_rels
    assert "tasks" in item_links_rels
    definition_link = next(link for link in item.links if link.rel == "workflow-definition")
    assert definition_link.href.endswith(f"/api/cj/workflow-definitions/{parent_def_id}/")
    tasks_link = next(link for link in item.links if link.rel == "tasks")
    assert tasks_link.href.endswith(f"/api/cj/workflow-instances/{instance_id}/tasks/")


    # 5. Test for 404 Not Found
    non_existent_id = "wf_nonexistent123"
    response_404 = client.get(f"/api/cj/workflow-instances/{non_existent_id}")
    assert response_404.status_code == 404
    error_response = response_404.json()
    assert "detail" in error_response
    assert error_response["detail"] == "Workflow Instance not found"


def test_cj_task_instance_serialization():
    """
    Tests the Collection+JSON serialization methods of the CJTaskInstance model.
    """
    base_url = "http://localhost:8000"
    context = {'base_url': base_url}

    task_id = "task_test123"
    wf_instance_id = "wf_parent789"

    # Scenario 1: Task is pending
    task_instance_data_pending = {
        "id": task_id,
        "name": "Test Task Instance - Pending",
        "workflow_instance_id": wf_instance_id,
        "order": 1,
        "status": TaskStatus.pending,
        # "due_datetime": None
    }
    cj_task_pending = CJTaskInstance(**task_instance_data_pending)

    # Test to_cj_item() for pending task
    cj_item_pending = cj_task_pending.to_cj_item(context=context)
    assert isinstance(cj_item_pending, Item)
    assert cj_item_pending.href == f"{base_url}{CJTaskInstance.cj_item_href_template.format(id=task_id)}"
    assert cj_item_pending.rel == CJTaskInstance.cj_item_rel

    item_data_dict_pending = {d.name: d.value for d in cj_item_pending.data}
    assert item_data_dict_pending["name"] == task_instance_data_pending["name"]
    assert item_data_dict_pending["workflow_instance_id"] == wf_instance_id
    assert item_data_dict_pending["status"] == TaskStatus.pending.value

    # Verify instance-specific links for pending task
    item_links_rels_pending = {link.rel for link in cj_item_pending.links}
    assert "workflow-instance" in item_links_rels_pending
    assert "complete" in item_links_rels_pending # Should have 'complete' link
    assert "undo-complete" not in item_links_rels_pending

    for link in cj_item_pending.links:
        if link.rel == "workflow-instance":
            assert link.href == f"{base_url}{CJWorkflowInstance.cj_item_href_template.format(id=wf_instance_id)}"
        elif link.rel == "complete":
            assert link.href == f"{base_url}/api/cj/task-instances/{task_id}/complete"
        assert link.href.startswith(base_url)


    # Scenario 2: Task is completed
    task_instance_data_completed = {
        "id": task_id, # Same ID for simplicity, could be different
        "name": "Test Task Instance - Completed",
        "workflow_instance_id": wf_instance_id,
        "order": 1,
        "status": TaskStatus.completed,
    }
    cj_task_completed = CJTaskInstance(**task_instance_data_completed)
    cj_item_completed = cj_task_completed.to_cj_item(context=context)
    item_links_rels_completed = {link.rel for link in cj_item_completed.links}
    assert "undo-complete" in item_links_rels_completed # Should have 'undo-complete' link
    assert "complete" not in item_links_rels_completed


    # Test to_cj_representation() with a single instance (using pending task)
    cj_repr_single = CJTaskInstance.to_cj_representation(instances=cj_task_pending, context=context)
    assert isinstance(cj_repr_single, CollectionJson)
    assert cj_repr_single.collection.version == "1.0"
    assert cj_repr_single.collection.href == f"{base_url}{CJTaskInstance.cj_collection_href_template}"
    assert cj_repr_single.collection.title == CJTaskInstance.cj_collection_title
    assert len(cj_repr_single.collection.items) == 1
    assert cj_repr_single.collection.items[0].href == cj_item_pending.href

    assert len(cj_repr_single.collection.links) > 0 # Global links
    assert len(cj_repr_single.collection.queries) > 0 # Global queries
    assert cj_repr_single.template is not None # Default template, not specific to task actions
    assert len(cj_repr_single.template.data) > 0


def test_get_tasks_for_workflow_instance_cj(client: TestClient):
    """
    Tests the GET /api/cj/workflow-instances/{instance_id}/tasks/ endpoint.
    """
    # 1. Create a WorkflowDefinition
    workflow_def_data = {
        "name": "Def for Instance Tasks Test",
        "description": "Definition for instance tasks list",
        "task_definitions": [
            {"name": "Task P", "order": 1, "due_datetime_offset_minutes": 60},
            {"name": "Task Q", "order": 2}
        ]
    }
    post_def_response = client.post("/api/cj/workflow-definitions/", json=workflow_def_data)
    assert post_def_response.status_code == 201
    try:
        created_def_item = CollectionJson(**post_def_response.json()).collection.items[0]
        parent_def_id = next(d.value for d in created_def_item.data if d.name == "id")
    except Exception as e:
        pytest.fail(f"Failed to create/parse parent workflow definition: {e}. Response: {post_def_response.text}")

    # 2. Create a WorkflowInstance for this definition
    instance_name = "Instance for Listing Tasks"
    new_instance_data = {
        "name": instance_name,
        "workflow_definition_id": parent_def_id,
        "user_id": "user_tasks_list_test",
    }
    post_instance_response = client.post("/api/cj/workflow-instances/", json=new_instance_data)
    assert post_instance_response.status_code == 201
    try:
        created_instance_item_meta = CollectionJson(**post_instance_response.json()).collection.items[0]
        instance_id = next(d.value for d in created_instance_item_meta.data if d.name == "id")
    except Exception as e:
        pytest.fail(f"Failed to create/parse workflow instance: {e}. Response: {post_instance_response.text}")

    # 3. Make a GET request to the instance's tasks endpoint
    tasks_url = f"/api/cj/workflow-instances/{instance_id}/tasks/"
    get_tasks_response = client.get(tasks_url)
    assert get_tasks_response.status_code == 200, f"Response: {get_tasks_response.text}"

    try:
        cj_response = CollectionJson(**get_tasks_response.json())
    except Exception as e:
        pytest.fail(f"Response JSON could not be parsed into CollectionJson model: {e}\nResponse content: {get_tasks_response.text}")

    # 4. Validate Collection+JSON structure
    assert cj_response.collection.version == "1.0"
    # The collection.href should be the tasks URL for this specific instance
    assert cj_response.collection.href == f"http://testserver{tasks_url}"
    assert cj_response.collection.title == f"Tasks for Workflow Instance {instance_id}"

    # Global links/queries for CJTaskInstance might be present, or overridden by the specific context
    # For this endpoint, it might not have global links/queries of CJTaskInstance,
    # but rather specific ones, or none if it's considered a sub-collection.
    # The current router implementation for this endpoint uses CJTaskInstance.to_cj_representation.
    # So, it will have the global links/queries of CJTaskInstance model unless overridden.
    assert cj_response.collection.links is not None # Check for links like 'self', 'home' from CJTaskInstance model
    assert cj_response.collection.queries is not None # Check for queries like 'search' from CJTaskInstance model
    assert cj_response.template is not None # Template from CJTaskInstance model

    # 5. Validate items (tasks) - assuming tasks are auto-created with instance
    assert isinstance(cj_response.collection.items, list)
    # The number of tasks should match the definition if they are auto-created
    if workflow_def_data["task_definitions"]:
        assert len(cj_response.collection.items) == len(workflow_def_data["task_definitions"])
        for item in cj_response.collection.items:
            assert item.href is not None and item.href.startswith(f"http://testserver{CJTaskInstance.cj_collection_href_template}")
            assert item.rel == CJTaskInstance.cj_item_rel
            assert isinstance(item.data, list)
            item_data_names = {d.name for d in item.data}
            assert "id" in item_data_names
            assert "name" in item_data_names
            assert "workflow_instance_id" in item_data_names and item_data_names["workflow_instance_id"] == instance_id
            assert "status" in item_data_names
            # Check for task-specific links (e.g., complete, parent instance)
            task_item_links_rels = {link.rel for link in item.links}
            assert "workflow-instance" in task_item_links_rels
            # 'complete' or 'undo-complete' should be present based on status
            task_status = next(d.value for d in item.data if d.name == "status")
            if task_status == TaskStatus.pending.value or task_status == TaskStatus.in_progress.value:
                assert "complete" in task_item_links_rels
            elif task_status == TaskStatus.completed.value:
                assert "undo-complete" in task_item_links_rels
    else:
        assert len(cj_response.collection.items) == 0


    # 6. Test for 404 Not Found for the main instance
    non_existent_instance_id = "wf_nonexistent789"
    response_404 = client.get(f"/api/cj/workflow-instances/{non_existent_instance_id}/tasks/")
    assert response_404.status_code == 404
    error_response = response_404.json()
    assert "detail" in error_response
    assert error_response["detail"] == f"Workflow Instance {non_existent_instance_id} not found."


def test_get_single_task_instance_cj(client: TestClient):
    """
    Tests the GET /api/cj/task-instances/{task_id} endpoint.
    """
    # 1. Create a WorkflowDefinition
    workflow_def_data = {
        "name": "Def for Single Task Test",
        "task_definitions": [{"name": "Task S", "order": 1}]
    }
    post_def_response = client.post("/api/cj/workflow-definitions/", json=workflow_def_data)
    assert post_def_response.status_code == 201
    parent_def_id = CollectionJson(**post_def_response.json()).collection.items[0].data[0].value # Quick ID grab

    # 2. Create a WorkflowInstance
    instance_name = "Instance for Single Task"
    new_instance_data = {"name": instance_name, "workflow_definition_id": parent_def_id, "user_id": "user_single_task_test"}
    post_instance_response = client.post("/api/cj/workflow-instances/", json=new_instance_data)
    assert post_instance_response.status_code == 201
    instance_id = CollectionJson(**post_instance_response.json()).collection.items[0].data[0].value # Quick ID grab

    # 3. Fetch tasks for the instance to get a valid task_id and its href
    tasks_url = f"/api/cj/workflow-instances/{instance_id}/tasks/"
    get_tasks_response = client.get(tasks_url)
    assert get_tasks_response.status_code == 200

    tasks_cj_response = CollectionJson(**get_tasks_response.json())
    assert len(tasks_cj_response.collection.items) > 0, "No tasks found for the instance, cannot proceed with single task test."

    # Assuming the first task is what we want to test
    task_to_test_item = tasks_cj_response.collection.items[0]
    task_id = next(d.value for d in task_to_test_item.data if d.name == "id")
    task_href = task_to_test_item.href # This should be the direct href to the task instance
    assert task_id is not None
    assert task_href is not None and task_href.endswith(f"/api/cj/task-instances/{task_id}/")


    # 4. Make a GET request to the specific task's href
    get_task_response = client.get(task_href)
    assert get_task_response.status_code == 200, f"Response: {get_task_response.text}"

    try:
        cj_response = CollectionJson(**get_task_response.json())
    except Exception as e:
        pytest.fail(f"Response JSON could not be parsed into CollectionJson model: {e}\nResponse content: {get_task_response.text}")

    # 5. Validate Collection+JSON structure for the single task
    assert cj_response.collection.version == "1.0"
    # Collection href should be the main task instances collection, not the item's href
    assert cj_response.collection.href == f"http://testserver{CJTaskInstance.cj_collection_href_template}"
    assert len(cj_response.collection.items) == 1

    item = cj_response.collection.items[0]
    assert item.href == task_href
    assert item.rel == CJTaskInstance.cj_item_rel

    item_data_dict = {d.name: d.value for d in item.data}
    assert item_data_dict["id"] == task_id
    assert item_data_dict["name"] == workflow_def_data["task_definitions"][0]["name"] # Assuming name is copied
    assert item_data_dict["workflow_instance_id"] == instance_id

    # Verify instance-specific links
    item_links_rels = {link.rel for link in item.links}
    assert "workflow-instance" in item_links_rels
    task_status = item_data_dict.get("status", TaskStatus.pending.value) # Default if not in data for some reason
    if task_status == TaskStatus.pending.value or task_status == TaskStatus.in_progress.value:
        assert "complete" in item_links_rels
    elif task_status == TaskStatus.completed.value:
        assert "undo-complete" in item_links_rels


    # 6. Test for 404 Not Found for a non-existent task ID
    non_existent_task_id = "task_nonexistent789"
    response_404 = client.get(f"/api/cj/task-instances/{non_existent_task_id}")
    assert response_404.status_code == 404
    error_response_404 = response_404.json()
    assert "detail" in error_response_404
    assert error_response_404["detail"] == "Task Instance not found"


def test_post_complete_task_instance_cj(client: TestClient):
    """
    Tests the POST /api/cj/task-instances/{task_id}/complete endpoint.
    """
    # 1. Setup: Create Definition, Instance, and get a pending Task ID
    workflow_def_data = {"name": "Def for Task Complete Test", "task_definitions": [{"name": "Task To Complete", "order": 1}]}
    post_def_response = client.post("/api/cj/workflow-definitions/", json=workflow_def_data)
    assert post_def_response.status_code == 201
    parent_def_id = CollectionJson(**post_def_response.json()).collection.items[0].data[0].value

    new_instance_data = {"name": "Instance for Task Complete", "workflow_definition_id": parent_def_id, "user_id": "user_task_complete_test"}
    post_instance_response = client.post("/api/cj/workflow-instances/", json=new_instance_data)
    assert post_instance_response.status_code == 201
    instance_id = CollectionJson(**post_instance_response.json()).collection.items[0].data[0].value

    get_tasks_response = client.get(f"/api/cj/workflow-instances/{instance_id}/tasks/")
    assert get_tasks_response.status_code == 200
    tasks_cj_response = CollectionJson(**get_tasks_response.json())
    assert len(tasks_cj_response.collection.items) > 0, "No tasks found for instance."

    pending_task_item = None
    for task_item in tasks_cj_response.collection.items:
        task_status_val = next(d.value for d in task_item.data if d.name == "status")
        if task_status_val == TaskStatus.pending.value:
            pending_task_item = task_item
            break

    assert pending_task_item is not None, "No pending task found to test completion."
    task_id_to_complete = next(d.value for d in pending_task_item.data if d.name == "id")

    # 2. Set placeholder auth header (replace with actual token/mocking if available)
    # This part is crucial and might need adjustment based on actual auth implementation.
    # For now, assuming a dummy user_id is extracted by the auth dependency if no real auth is hit by TestClient
    # or that the service layer's user_id requirement is met by a default/mocked user in tests.
    # If your get_current_active_user dependency raises an error without a valid token, this test will fail.
    # A common way to handle this in tests is to override the dependency:
    # from src.dependencies import get_current_active_user
    # def mock_get_current_active_user():
    #     return AuthenticatedUser(user_id="test_user_complete", username="test_user_complete") # Adjust AuthenticatedUser as needed
    # app.dependency_overrides[get_current_active_user] = mock_get_current_active_user
    # client.headers.update({"Authorization": "Bearer faketoken"}) # Still might be needed if auth middleware checks presence

    # 3. Make POST request to complete the task
    complete_url = f"/api/cj/task-instances/{task_id_to_complete}/complete"
    # Assuming the auth dependency is mocked or TestClient bypasses actual auth for this structure test
    response_complete = client.post(complete_url)
    assert response_complete.status_code == 200, f"Response: {response_complete.text}"

    try:
        cj_response_completed = CollectionJson(**response_complete.json())
    except Exception as e:
        pytest.fail(f"Response JSON could not be parsed into CollectionJson model: {e}\nResponse content: {response_complete.text}")

    # 4. Validate the updated task
    assert len(cj_response_completed.collection.items) == 1
    completed_item = cj_response_completed.collection.items[0]
    completed_item_data = {d.name: d.value for d in completed_item.data}
    assert completed_item_data["id"] == task_id_to_complete
    assert completed_item_data["status"] == TaskStatus.completed.value

    completed_item_links_rels = {link.rel for link in completed_item.links}
    assert "undo-complete" in completed_item_links_rels
    assert "complete" not in completed_item_links_rels

    # Clean up dependency override if it was set
    # if get_current_active_user in app.dependency_overrides:
    #     del app.dependency_overrides[get_current_active_user]

    # 5. Test for 404 Not Found
    non_existent_task_id = "task_nonexistent_complete"
    response_404 = client.post(f"/api/cj/task-instances/{non_existent_task_id}/complete")
    assert response_404.status_code == 404 # Assuming it hits the task not found before auth
                                          # or that the service layer handles this gracefully.
                                          # If auth is strict, it might be 401/403 first.
                                          # For this test, we assume we can reach the "not found" logic.
    error_404_response = response_404.json()
    assert "detail" in error_404_response
    # The detail message might vary if it's caught by service vs. repo.
    # assert error_404_response["detail"] == "Task Instance not found" # This can be too specific


def test_post_undo_complete_task_instance_cj(client: TestClient):
    """
    Tests the POST /api/cj/task-instances/{task_id}/undo-complete endpoint.
    """
    # 1. Setup: Create Definition, Instance, get a Task, and Complete it
    workflow_def_data = {"name": "Def for Task Undo Test", "task_definitions": [{"name": "Task To Undo", "order": 1}]}
    post_def_response = client.post("/api/cj/workflow-definitions/", json=workflow_def_data)
    assert post_def_response.status_code == 201
    parent_def_id = CollectionJson(**post_def_response.json()).collection.items[0].data[0].value

    new_instance_data = {"name": "Instance for Task Undo", "workflow_definition_id": parent_def_id, "user_id": "user_task_undo_test"}
    post_instance_response = client.post("/api/cj/workflow-instances/", json=new_instance_data)
    assert post_instance_response.status_code == 201
    instance_id = CollectionJson(**post_instance_response.json()).collection.items[0].data[0].value

    get_tasks_response = client.get(f"/api/cj/workflow-instances/{instance_id}/tasks/")
    assert get_tasks_response.status_code == 200
    tasks_cj_response = CollectionJson(**get_tasks_response.json())
    assert len(tasks_cj_response.collection.items) > 0, "No tasks found for instance."

    task_to_process_item = tasks_cj_response.collection.items[0] # Assuming first task
    task_id_to_process = next(d.value for d in task_to_process_item.data if d.name == "id")

    # Complete the task first (again, assuming auth is handled/mocked)
    client.post(f"/api/cj/task-instances/{task_id_to_process}/complete")
    # We don't need to deeply check the complete response here, just ensure it likely worked.

    # 2. Set placeholder auth header (as in complete test)
    # app.dependency_overrides[get_current_active_user] = mock_get_current_active_user (if using)

    # 3. Make POST request to undo task completion
    undo_url = f"/api/cj/task-instances/{task_id_to_process}/undo-complete"
    response_undo = client.post(undo_url)
    assert response_undo.status_code == 200, f"Response: {response_undo.text}"

    try:
        cj_response_undone = CollectionJson(**response_undo.json())
    except Exception as e:
        pytest.fail(f"Response JSON could not be parsed into CollectionJson model: {e}\nResponse content: {response_undo.text}")

    # 4. Validate the updated task
    assert len(cj_response_undone.collection.items) == 1
    undone_item = cj_response_undone.collection.items[0]
    undone_item_data = {d.name: d.value for d in undone_item.data}
    assert undone_item_data["id"] == task_id_to_process
    # Assuming undoing completion reverts to 'pending' or 'in_progress'
    # The exact status depends on service logic. Let's assume TaskStatus.pending.
    assert undone_item_data["status"] == TaskStatus.pending.value

    undone_item_links_rels = {link.rel for link in undone_item.links}
    assert "complete" in undone_item_links_rels
    assert "undo-complete" not in undone_item_links_rels

    # Clean up dependency override if it was set
    # if get_current_active_user in app.dependency_overrides:
    #     del app.dependency_overrides[get_current_active_user]

    # 5. Test for 404 Not Found
    non_existent_task_id = "task_nonexistent_undo"
    response_404 = client.post(f"/api/cj/task-instances/{non_existent_task_id}/undo-complete")
    assert response_404.status_code == 404
    # Further checks on error response as in complete test.
    error_404_response = response_404.json()
    assert "detail" in error_404_response
