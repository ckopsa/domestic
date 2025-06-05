from __future__ import annotations

from typing import Optional, List, Dict, Any, ClassVar, Union

from pydantic import BaseModel, Field as PydanticField, computed_field
from pydantic_core import PydanticUndefined


class Link(BaseModel):
    rel: str
    href: str
    prompt: Optional[str] = None
    render: Optional[str] = None
    media_type: Optional[str] = None
    method: Optional[str] = PydanticField("GET", description="HTTP method for the link")


class ItemData(BaseModel):
    name: str
    value: Union[str, bool, int, float, dict, list, None] = PydanticField(None, description="Value of the data item")
    prompt: Optional[str] = PydanticField(None, description="Human Readable prompt for the data")
    type: Optional[str] = PydanticField(None, description="Type of the data")


class QueryData(ItemData):
    pass


class TemplateData(QueryData):
    required: Optional[bool] = False


class Query(BaseModel):
    rel: str
    href: str
    prompt: Optional[str] = None
    name: Optional[str] = None
    data: List[QueryData] = PydanticField(default_factory=list)


class Item(BaseModel):
    href: str
    rel: str
    data: List[ItemData] = PydanticField(default_factory=list)
    links: List[Link] = PydanticField(default_factory=list)


class Collection(BaseModel):
    version: str = "1.0"
    href: str
    title: str
    links: List[Link] = PydanticField(default_factory=list)
    items: List[Item] = PydanticField(default_factory=list)
    queries: List[Query] = PydanticField(default_factory=list)


class Template(BaseModel):
    data: List[TemplateData] = PydanticField(default_factory=list)
    prompt: Optional[str] = None


class Error(BaseModel):
    title: str
    code: int
    message: str
    details: Optional[str] = None


class CollectionJson(BaseModel):
    collection: Collection
    template: Optional[Template] = PydanticField(None, description="Template for the collection")
    error: Optional[Error] = PydanticField(None, description="Error details, if any")



class CollectionJSONRepresentable(BaseModel):
    cj_collection_href_template: ClassVar[str] = "/items/"
    cj_item_href_template: ClassVar[str] = "/items/{id}/"
    cj_item_rel: ClassVar[str] = "item"
    cj_collection_title: ClassVar[str] = "Items Collection"
    cj_version: ClassVar[str] = "1.0"
    cj_global_links: ClassVar[List[Link]] = []
    cj_global_queries: ClassVar[List[Query]] = []

    id: Union[int, str, None] = PydanticField(None, title="Identifier", json_schema_extra={"cj_read_only": True})


    @classmethod
    def _get_base_url_from_context(cls, context: Optional[Dict[str, Any]] = None) -> str:
        return context.get("base_url", "") if context else ""

    @classmethod
    def _resolve_href(cls, template: str, base_url: str, **kwargs) -> str:
        full_template = (base_url.rstrip('/') + "/" + template.lstrip('/'))
        return full_template.format(**kwargs)

    @classmethod
    def get_cj_template_data_definitions(cls, context: Optional[Dict[str, Any]] = None) -> List[TemplateData]:
        template_data_list: List[TemplateData] = []
        for field_name, field_info in cls.model_fields.items():
            json_extra = field_info.json_schema_extra or {}
            if json_extra.get("cj_internal") or json_extra.get("cj_read_only_for_template",
                                                               json_extra.get("cj_read_only")):
                continue

            prompt = field_info.title or field_name.replace('_', ' ').capitalize()
            default_value = field_info.get_default(call_default_factory=True)

            value_for_template: Optional[str] = ""
            if default_value is not None and default_value is not PydanticUndefined:
                value_for_template = str(default_value)

            td_dict: Dict[str, Any] = {
                "name": field_info.alias or field_name,
                "value": value_for_template,
                "prompt": prompt,
                "required": field_info.is_required()
            }

            if cj_type := json_extra.get("cj_type"):
                td_dict["type"] = cj_type

            for k, v in json_extra.items():
                if k.startswith("cj_template_attr_"):
                    td_dict[k.replace("cj_template_attr_", "")] = v

            template_data_list.append(TemplateData(**td_dict))
        return template_data_list

    @classmethod
    def get_cj_write_template(cls, prompt_override: Optional[str] = None,
                              context: Optional[Dict[str, Any]] = None) -> Template:
        template_data = cls.get_cj_template_data_definitions(context=context)
        return Template(data=template_data, prompt=prompt_override or f"New {cls.cj_collection_title}")

    @computed_field(description="The Collection+JSON href for this item")
    @property
    def cj_href(self) -> Optional[str]:
        if self.id is not None:
            return self.__class__.cj_item_href_template.format(id=self.id)
        return None

    def get_cj_instance_item_data(self, context: Optional[Dict[str, Any]] = None) -> List[ItemData]:
        item_data_list: List[ItemData] = []
        instance_dict = self.model_dump(exclude={"cj_href"}, by_alias=True, mode='python')

        for field_name, field_info in self.__class__.model_fields.items():
            json_extra = field_info.json_schema_extra or {}
            if json_extra.get("cj_internal") or field_name == "cj_href":
                continue

            dict_key = field_info.alias or field_name
            value = instance_dict.get(dict_key)
            prompt = field_info.title or field_name.replace('_', ' ').capitalize()

            id_dict: Dict[str, Any] = {"name": dict_key, "value": value, "prompt": prompt}

            if cj_type := json_extra.get("cj_type"):
                id_dict["type"] = cj_type

            for k, v in json_extra.items():
                if k.startswith("cj_item_attr_"):
                    id_dict[k.replace("cj_item_attr_", "")] = v

            item_data_list.append(ItemData(**id_dict))
        return item_data_list

    def get_cj_instance_item_links(self, base_url: str = "") -> List[Link]:
        links: List[Link] = []
        if self.cj_href:
            resolved_cj_href = self._resolve_href(self.cj_href, base_url=base_url)
            links.append(Link(rel="edit", href=resolved_cj_href, prompt=f"Edit {self.__class__.__name__}", method="GET"))
            links.append(Link(rel="delete", href=resolved_cj_href, prompt=f"Delete {self.__class__.__name__}", method="DELETE"))
        return links

    def to_cj_item(self, context: Optional[Dict[str, Any]] = None) -> Item:
        base_url = self._get_base_url_from_context(context)
        item_rel_from_config = (self.model_config or {}).get("cj_item_rel", self.__class__.cj_item_rel)
        resolved_cj_href = self._resolve_href(self.cj_href or "", base_url=base_url) if self.cj_href else self._resolve_href(self.__class__.cj_item_href_template.format(id="undefined"), base_url=base_url)

        return Item(
            href=resolved_cj_href,
            rel=item_rel_from_config,
            data=self.get_cj_instance_item_data(context=context),
            links=self.get_cj_instance_item_links(base_url=base_url)
        )

    @classmethod
    def to_cj_representation(cls,
                             instances: Union[Optional[BaseModel], List[BaseModel]] = None,
                             collection_links_override: Optional[List[Link]] = None,
                             collection_queries_override: Optional[List[Query]] = None,
                             collection_title_override: Optional[str] = None,
                             error_details: Optional[Error] = None,
                             context: Optional[Dict[str, Any]] = None
                             ) -> CollectionJson:
        base_url = cls._get_base_url_from_context(context)
        collection_href = cls._resolve_href(cls.cj_collection_href_template, base_url=base_url)

        global_links = [
            Link(**{**link_def.model_dump(), "href": cls._resolve_href(link_def.href, base_url=base_url)})
            for link_def in (collection_links_override or cls.cj_global_links)
        ]
        global_queries = [
            Query(**{**query_def.model_dump(), "href": cls._resolve_href(query_def.href, base_url=base_url)})
            for query_def in (collection_queries_override or cls.cj_global_queries)
        ]

        items_list: List[Item] = []
        if instances:
            instance_list = instances if isinstance(instances, list) else [instances]
            items_list = [inst.to_cj_item(context=context) for inst in instance_list if isinstance(inst, cls)]

        collection_obj = Collection(
            version=cls.cj_version,
            href=collection_href,
            title=collection_title_override or cls.cj_collection_title,
            links=global_links,
            items=items_list,
            queries=global_queries
        )
        template_obj = cls.get_cj_write_template(context=context)

        return CollectionJson(collection=collection_obj, template=template_obj, error=error_details)
if __name__ == "__main__":
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
                        Link(rel="mark-complete", href=f"{resolved_item_href}/complete", prompt="Mark as Complete",
                             method="POST"))
                else:
                    links.append(Link(rel="mark-incomplete", href=f"{resolved_item_href}/incomplete",
                                      prompt="Mark as Incomplete", method="POST"))
            return links


    test_context = {"base_url": "https://api.example.com"}
    task1 = TaskDefinition(id=1, name="Finalize Q2 report", order=1, is_completed=False,
                           description="Review and send out the final Q2 performance report.")
    task2 = TaskDefinition(id=2, name="Plan team offsite", order=2, is_completed=True)
    all_tasks = [task1, task2]

    print("=" * 50)
    print("✅ 1. TESTING TEMPLATE GENERATION")
    print("-" * 50)
    template_obj = TaskDefinition.get_cj_write_template(context=test_context)
    print(template_obj.model_dump_json(indent=2))

    print("\n" + "=" * 50)
    print("✅ 2. TESTING SINGLE ITEM REPRESENTATION (Incomplete Task)")
    print("-" * 50)
    item_obj_1 = task1.to_cj_item(context=test_context)
    print(item_obj_1.model_dump_json(indent=2))

    print("\n" + "=" * 50)
    print("✅ 3. TESTING SINGLE ITEM REPRESENTATION (Completed Task)")
    print("-" * 50)
    item_obj_2 = task2.to_cj_item(context=test_context)
    print(item_obj_2.model_dump_json(indent=2))

    print("\n" + "=" * 50)
    print("✅ 4. TESTING EMPTY COLLECTION REPRESENTATION")
    print("-" * 50)
    empty_collection_json = TaskDefinition.to_cj_representation(context=test_context)
    print(empty_collection_json.model_dump_json(indent=2))

    print("\n" + "=" * 50)
    print("✅ 5. TESTING FULL COLLECTION REPRESENTATION")
    print("-" * 50)
    full_collection_json = TaskDefinition.to_cj_representation(instances=all_tasks, context=test_context)
    print(full_collection_json.model_dump_json(indent=2))

    print("\n" + "=" * 50)
    print("✅ 6. TESTING SINGLE ITEM WRAPPED IN COLLECTION")
    print("-" * 50)
    single_item_collection_json = TaskDefinition.to_cj_representation(instances=task1, context=test_context)
    print(single_item_collection_json.model_dump_json(indent=2))
