import json
from typing import Optional, List, ClassVar, Dict, Any, Union

from pydantic import Field as PydanticField, BaseModel

from src.cj_models import (
    CollectionJSONRepresentable,
    Link,
    Query,
    QueryData,
    TemplateData,
    ItemData,
    Template,
    Item,
    Collection,
    CollectionJson,
    Error
)


def test_task_definition_cj_representation():
    class TaskDefinition(CollectionJSONRepresentable):
        cj_collection_href_template: ClassVar[str] = "/tasks/"
        cj_item_href_template: ClassVar[str] = "/tasks/{id}/"
        cj_item_rel: ClassVar[str] = "task"
        cj_collection_title: ClassVar[str] = "Task Definitions"

        cj_global_links: ClassVar[List[Link]] = [
            Link(rel="self", href="/tasks/", prompt="All Tasks"),
            Link(rel="home", href="/", prompt="API Home")
        ]
        cj_global_queries: ClassVar[List[Query]] = [
            Query(
                rel="search", href="/tasks/search", prompt="Search Tasks", name="search_tasks",
                data=[
                    QueryData(name="name_query", value="", prompt="Name contains", type="text"),
                    QueryData(name="completed_status", value="", prompt="Completed Status (true/false)", type="boolean")
                ]
            )
        ]

        id: Optional[int] = PydanticField(None, title="Task ID", json_schema_extra={"cj_read_only": True})
        name: str = PydanticField(..., title="Task Name", description="The name of the task.")
        order: int = PydanticField(..., title="Display Order")
        is_completed: bool = PydanticField(False, title="Completed", json_schema_extra={"cj_type": "boolean"})
        description: Optional[str] = PydanticField(None, title="Description", json_schema_extra={"cj_type": "textarea"})

        def get_cj_instance_item_links(self, base_url: str = "") -> List[Link]:
            links = super().get_cj_instance_item_links(base_url=base_url)
            if self.cj_href:
                resolved_item_href = self._resolve_href(self.cj_href, base_url=base_url)
                if not self.is_completed:
                    links.append(
                        Link(rel="mark-complete", href=f"{resolved_item_href.rstrip('/')}/complete", prompt="Mark as Complete",
                             method="POST"))
                else:
                    links.append(Link(rel="mark-incomplete", href=f"{resolved_item_href.rstrip('/')}/incomplete",
                                      prompt="Mark as Incomplete", method="POST"))
            return links

    test_context = {"base_url": "https://api.example.com"}
    task1 = TaskDefinition(id=1, name="Finalize Q2 report", order=1, is_completed=False,
                           description="Review and send out the final Q2 performance report.")
    task2 = TaskDefinition(id=2, name="Plan team offsite", order=2, is_completed=True)
    all_tasks = [task1, task2]

    # Test 1: Template Generation
    template_obj = TaskDefinition.get_cj_write_template(context=test_context)
    actual_json_1 = template_obj.model_dump_json(indent=2)
    expected_json_1 = """
{
  "data": [
    {
      "name": "name",
      "value": "",
      "prompt": "Task Name",
      "required": true,
      "type": null
    },
    {
      "name": "order",
      "value": "",
      "prompt": "Display Order",
      "required": true,
      "type": null
    },
    {
      "name": "is_completed",
      "value": "False",
      "prompt": "Completed",
      "required": false,
      "type": "boolean"
    },
    {
      "name": "description",
      "value": "",
      "prompt": "Description",
      "required": false,
      "type": "textarea"
    }
  ],
  "prompt": "New Task Definitions"
}
"""
    assert json.loads(actual_json_1) == json.loads(expected_json_1.strip())

    # Test 2: Single Item Representation (Incomplete Task)
    item_obj_1 = task1.to_cj_item(context=test_context)
    actual_json_2 = item_obj_1.model_dump_json(indent=2)
    expected_json_2 = """
{
  "href": "https://api.example.com/tasks/1/",
  "rel": "task",
  "data": [
    {
      "name": "id",
      "value": 1,
      "prompt": "Task ID",
      "type": null
    },
    {
      "name": "name",
      "value": "Finalize Q2 report",
      "prompt": "Task Name",
      "type": null
    },
    {
      "name": "order",
      "value": 1,
      "prompt": "Display Order",
      "type": null
    },
    {
      "name": "is_completed",
      "value": false,
      "prompt": "Completed",
      "type": "boolean"
    },
    {
      "name": "description",
      "value": "Review and send out the final Q2 performance report.",
      "prompt": "Description",
      "type": "textarea"
    }
  ],
  "links": [
    {
      "rel": "edit",
      "href": "https://api.example.com/tasks/1/",
      "prompt": "Edit TaskDefinition",
      "render": null,
      "media_type": null,
      "method": "GET"
    },
    {
      "rel": "delete",
      "href": "https://api.example.com/tasks/1/",
      "prompt": "Delete TaskDefinition",
      "render": null,
      "media_type": null,
      "method": "DELETE"
    },
    {
      "rel": "mark-complete",
      "href": "https://api.example.com/tasks/1/complete",
      "prompt": "Mark as Complete",
      "render": null,
      "media_type": null,
      "method": "POST"
    }
  ]
}
"""
    assert json.loads(actual_json_2) == json.loads(expected_json_2.strip())

    # Test 3: Single Item Representation (Completed Task)
    item_obj_2 = task2.to_cj_item(context=test_context)
    actual_json_3 = item_obj_2.model_dump_json(indent=2)
    expected_json_3 = """
{
  "href": "https://api.example.com/tasks/2/",
  "rel": "task",
  "data": [
    {
      "name": "id",
      "value": 2,
      "prompt": "Task ID",
      "type": null
    },
    {
      "name": "name",
      "value": "Plan team offsite",
      "prompt": "Task Name",
      "type": null
    },
    {
      "name": "order",
      "value": 2,
      "prompt": "Display Order",
      "type": null
    },
    {
      "name": "is_completed",
      "value": true,
      "prompt": "Completed",
      "type": "boolean"
    },
    {
      "name": "description",
      "value": null,
      "prompt": "Description",
      "type": "textarea"
    }
  ],
  "links": [
    {
      "rel": "edit",
      "href": "https://api.example.com/tasks/2/",
      "prompt": "Edit TaskDefinition",
      "render": null,
      "media_type": null,
      "method": "GET"
    },
    {
      "rel": "delete",
      "href": "https://api.example.com/tasks/2/",
      "prompt": "Delete TaskDefinition",
      "render": null,
      "media_type": null,
      "method": "DELETE"
    },
    {
      "rel": "mark-incomplete",
      "href": "https://api.example.com/tasks/2/incomplete",
      "prompt": "Mark as Incomplete",
      "render": null,
      "media_type": null,
      "method": "POST"
    }
  ]
}
"""
    assert json.loads(actual_json_3) == json.loads(expected_json_3.strip())

    # Test 4: Empty Collection Representation
    empty_collection_json_obj = TaskDefinition.to_cj_representation(context=test_context)
    actual_json_4 = empty_collection_json_obj.model_dump_json(indent=2)
    expected_json_4 = """
{
  "collection": {
    "version": "1.0",
    "href": "https://api.example.com/tasks/",
    "title": "Task Definitions",
    "links": [
      {
        "rel": "self",
        "href": "https://api.example.com/tasks/",
        "prompt": "All Tasks",
        "render": null,
        "media_type": null,
        "method": "GET"
      },
      {
        "rel": "home",
        "href": "https://api.example.com/",
        "prompt": "API Home",
        "render": null,
        "media_type": null,
        "method": "GET"
      }
    ],
    "items": [],
    "queries": [
      {
        "rel": "search",
        "href": "https://api.example.com/tasks/search",
        "prompt": "Search Tasks",
        "name": "search_tasks",
        "data": [
          {
            "name": "name_query",
            "value": "",
            "prompt": "Name contains",
            "type": "text"
          },
          {
            "name": "completed_status",
            "value": "",
            "prompt": "Completed Status (true/false)",
            "type": "boolean"
          }
        ]
      }
    ]
  },
  "template": {
    "data": [
      {
        "name": "name",
        "value": "",
        "prompt": "Task Name",
        "required": true,
        "type": null
      },
      {
        "name": "order",
        "value": "",
        "prompt": "Display Order",
        "required": true,
        "type": null
      },
      {
        "name": "is_completed",
        "value": "False",
        "prompt": "Completed",
        "required": false,
        "type": "boolean"
      },
      {
        "name": "description",
        "value": "",
        "prompt": "Description",
        "required": false,
        "type": "textarea"
      }
    ],
    "prompt": "New Task Definitions"
  },
  "error": null
}
"""
    assert json.loads(actual_json_4) == json.loads(expected_json_4.strip())

    # Test 5: Full Collection Representation
    full_collection_json_obj = TaskDefinition.to_cj_representation(instances=all_tasks, context=test_context)
    actual_json_5 = full_collection_json_obj.model_dump_json(indent=2)
    expected_json_5 = """
{
  "collection": {
    "version": "1.0",
    "href": "https://api.example.com/tasks/",
    "title": "Task Definitions",
    "links": [
      {
        "rel": "self",
        "href": "https://api.example.com/tasks/",
        "prompt": "All Tasks",
        "render": null,
        "media_type": null,
        "method": "GET"
      },
      {
        "rel": "home",
        "href": "https://api.example.com/",
        "prompt": "API Home",
        "render": null,
        "media_type": null,
        "method": "GET"
      }
    ],
    "items": [
      {
        "href": "https://api.example.com/tasks/1/",
        "rel": "task",
        "data": [
          {
            "name": "id",
            "value": 1,
            "prompt": "Task ID",
            "type": null
          },
          {
            "name": "name",
            "value": "Finalize Q2 report",
            "prompt": "Task Name",
            "type": null
          },
          {
            "name": "order",
            "value": 1,
            "prompt": "Display Order",
            "type": null
          },
          {
            "name": "is_completed",
            "value": false,
            "prompt": "Completed",
            "type": "boolean"
          },
          {
            "name": "description",
            "value": "Review and send out the final Q2 performance report.",
            "prompt": "Description",
            "type": "textarea"
          }
        ],
        "links": [
          {
            "rel": "edit",
            "href": "https://api.example.com/tasks/1/",
            "prompt": "Edit TaskDefinition",
            "render": null,
            "media_type": null,
            "method": "GET"
          },
          {
            "rel": "delete",
            "href": "https://api.example.com/tasks/1/",
            "prompt": "Delete TaskDefinition",
            "render": null,
            "media_type": null,
            "method": "DELETE"
          },
          {
            "rel": "mark-complete",
            "href": "https://api.example.com/tasks/1/complete",
            "prompt": "Mark as Complete",
            "render": null,
            "media_type": null,
            "method": "POST"
          }
        ]
      },
      {
        "href": "https://api.example.com/tasks/2/",
        "rel": "task",
        "data": [
          {
            "name": "id",
            "value": 2,
            "prompt": "Task ID",
            "type": null
          },
          {
            "name": "name",
            "value": "Plan team offsite",
            "prompt": "Task Name",
            "type": null
          },
          {
            "name": "order",
            "value": 2,
            "prompt": "Display Order",
            "type": null
          },
          {
            "name": "is_completed",
            "value": true,
            "prompt": "Completed",
            "type": "boolean"
          },
          {
            "name": "description",
            "value": null,
            "prompt": "Description",
            "type": "textarea"
          }
        ],
        "links": [
          {
            "rel": "edit",
            "href": "https://api.example.com/tasks/2/",
            "prompt": "Edit TaskDefinition",
            "render": null,
            "media_type": null,
            "method": "GET"
          },
          {
            "rel": "delete",
            "href": "https://api.example.com/tasks/2/",
            "prompt": "Delete TaskDefinition",
            "render": null,
            "media_type": null,
            "method": "DELETE"
          },
          {
            "rel": "mark-incomplete",
            "href": "https://api.example.com/tasks/2/incomplete",
            "prompt": "Mark as Incomplete",
            "render": null,
            "media_type": null,
            "method": "POST"
          }
        ]
      }
    ],
    "queries": [
      {
        "rel": "search",
        "href": "https://api.example.com/tasks/search",
        "prompt": "Search Tasks",
        "name": "search_tasks",
        "data": [
          {
            "name": "name_query",
            "value": "",
            "prompt": "Name contains",
            "type": "text"
          },
          {
            "name": "completed_status",
            "value": "",
            "prompt": "Completed Status (true/false)",
            "type": "boolean"
          }
        ]
      }
    ]
  },
  "template": {
    "data": [
      {
        "name": "name",
        "value": "",
        "prompt": "Task Name",
        "required": true,
        "type": null
      },
      {
        "name": "order",
        "value": "",
        "prompt": "Display Order",
        "required": true,
        "type": null
      },
      {
        "name": "is_completed",
        "value": "False",
        "prompt": "Completed",
        "required": false,
        "type": "boolean"
      },
      {
        "name": "description",
        "value": "",
        "prompt": "Description",
        "required": false,
        "type": "textarea"
      }
    ],
    "prompt": "New Task Definitions"
  },
  "error": null
}
"""
    assert json.loads(actual_json_5) == json.loads(expected_json_5.strip())

    # Test 6: Single Item Wrapped in Collection
    single_item_collection_json_obj = TaskDefinition.to_cj_representation(instances=task1, context=test_context)
    actual_json_6 = single_item_collection_json_obj.model_dump_json(indent=2)
    expected_json_6 = """
{
  "collection": {
    "version": "1.0",
    "href": "https://api.example.com/tasks/",
    "title": "Task Definitions",
    "links": [
      {
        "rel": "self",
        "href": "https://api.example.com/tasks/",
        "prompt": "All Tasks",
        "render": null,
        "media_type": null,
        "method": "GET"
      },
      {
        "rel": "home",
        "href": "https://api.example.com/",
        "prompt": "API Home",
        "render": null,
        "media_type": null,
        "method": "GET"
      }
    ],
    "items": [
      {
        "href": "https://api.example.com/tasks/1/",
        "rel": "task",
        "data": [
          {
            "name": "id",
            "value": 1,
            "prompt": "Task ID",
            "type": null
          },
          {
            "name": "name",
            "value": "Finalize Q2 report",
            "prompt": "Task Name",
            "type": null
          },
          {
            "name": "order",
            "value": 1,
            "prompt": "Display Order",
            "type": null
          },
          {
            "name": "is_completed",
            "value": false,
            "prompt": "Completed",
            "type": "boolean"
          },
          {
            "name": "description",
            "value": "Review and send out the final Q2 performance report.",
            "prompt": "Description",
            "type": "textarea"
          }
        ],
        "links": [
          {
            "rel": "edit",
            "href": "https://api.example.com/tasks/1/",
            "prompt": "Edit TaskDefinition",
            "render": null,
            "media_type": null,
            "method": "GET"
          },
          {
            "rel": "delete",
            "href": "https://api.example.com/tasks/1/",
            "prompt": "Delete TaskDefinition",
            "render": null,
            "media_type": null,
            "method": "DELETE"
          },
          {
            "rel": "mark-complete",
            "href": "https://api.example.com/tasks/1/complete",
            "prompt": "Mark as Complete",
            "render": null,
            "media_type": null,
            "method": "POST"
          }
        ]
      }
    ],
    "queries": [
      {
        "rel": "search",
        "href": "https://api.example.com/tasks/search",
        "prompt": "Search Tasks",
        "name": "search_tasks",
        "data": [
          {
            "name": "name_query",
            "value": "",
            "prompt": "Name contains",
            "type": "text"
          },
          {
            "name": "completed_status",
            "value": "",
            "prompt": "Completed Status (true/false)",
            "type": "boolean"
          }
        ]
      }
    ]
  },
  "template": {
    "data": [
      {
        "name": "name",
        "value": "",
        "prompt": "Task Name",
        "required": true,
        "type": null
      },
      {
        "name": "order",
        "value": "",
        "prompt": "Display Order",
        "required": true,
        "type": null
      },
      {
        "name": "is_completed",
        "value": "False",
        "prompt": "Completed",
        "required": false,
        "type": "boolean"
      },
      {
        "name": "description",
        "value": "",
        "prompt": "Description",
        "required": false,
        "type": "textarea"
      }
    ],
    "prompt": "New Task Definitions"
  },
  "error": null
}
"""
    assert json.loads(actual_json_6) == json.loads(expected_json_6.strip())
