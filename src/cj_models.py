from __future__ import annotations

from typing import Optional, List, Dict, Any, ClassVar, Union

from pydantic import BaseModel, Field as PydanticField, computed_field


class Link(BaseModel):
    rel: str
    href: str
    prompt: Optional[str] = None
    render: Optional[str] = None  # e.g., "link", "image", "text"
    media_type: Optional[str] = None  # e.g., "application/json", "text/html"
    method: Optional[str] = PydanticField("GET", description="HTTP method for the link",
                                          examples=["GET", "POST", "PUT", "DELETE"])


class ItemData(BaseModel):
    name: str
    value: str | bool | int | float | dict | list | None = PydanticField(None,
                                                                         description="Value of the data item")
    prompt: Optional[str] = PydanticField(None, description="Human Readable prompt for the data")
    type: Optional[str] = PydanticField(None, description="Type of the data", examples=["text", "number", "boolean"])


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


class CollectionJson(BaseModel):  # User's top-level model
    collection: Collection
    template: Optional[Template] = PydanticField(None, description="Template for the collection")
    error: Optional[Error] = PydanticField(None, description="Error details, if any")


# --- Adapted Collection+JSON Mixin ---
class CollectionJSONRepresentable(BaseModel):
    cj_collection_href_template: ClassVar[str] = "/items/"
    cj_item_href_template: ClassVar[str] = "/items/{id}/"
    cj_item_rel: ClassVar[str] = "item"
    cj_collection_title: ClassVar[str] = "Items Collection"
    cj_version: ClassVar[str] = "1.0"

    cj_global_links: ClassVar[List[Link]] = []  # Expects dicts that can init Link
    cj_global_queries: ClassVar[List[Query]] = []  # Expects dicts that can init Query

    id: Union[int, str, None] = PydanticField(None, title="Identifier", json_schema_extra={"cj_read_only": True})

    @classmethod
    def _get_base_url_from_context(cls, context: Optional[Dict[str, Any]] = None) -> str:
        return context.get("base_url", "") if context else ""

    @classmethod
    def _resolve_href(cls, template: str, base_url: str, **kwargs) -> str:
        # Ensure no double slashes
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
            default_value = field_info.get_default(call_default_factory=True)  # Can be None or Ellipsis

            # Convert complex default values or Ellipsis to representable string for template 'value'
            value_for_template: Optional[str] = None
            if default_value is not None and default_value is not Ellipsis:
                value_for_template = str(default_value)
            else:  # No default or default is None
                value_for_template = ""

            td_dict: Dict[str, Any] = {
                "name": field_info.alias or field_name,
                "value": value_for_template,
                "prompt": prompt,
                "required": field_info.is_required()
            }

            if json_extra.get("cj_type"): td_dict["type"] = json_extra["cj_type"]
            # Add other Cj template metadata from json_schema_extra
            # e.g. cj_template_pattern, cj_template_options (for select/radio)
            for k, v in json_extra.items():
                if k.startswith("cj_template_attr_"):  # e.g. cj_template_attr_pattern
                    td_dict[k.replace("cj_template_attr_", "")] = v

            template_data_list.append(TemplateData(**td_dict))
        return template_data_list

    @classmethod
    def get_cj_write_template(cls, prompt_override: Optional[str] = None,
                              context: Optional[Dict[str, Any]] = None) -> Template:
        template_data = cls.get_cj_template_data_definitions(context=context)
        return Template(data=template_data, prompt=prompt_override or cls.cj_collection_title)

    @computed_field(description="The Collection+JSON href for this item")
    @property
    def cj_href(self) -> Optional[str]:
        """Computes the item's href. For full URL, context might be needed by caller."""
        if self.id is not None:
            # This will be a relative path template. Caller (e.g. to_cj_item) needs to add base_url.
            return self.__class__.cj_item_href_template.format(id=self.id)
        return None

    def get_cj_instance_item_data(self, context: Optional[Dict[str, Any]] = None) -> List[ItemData]:
        item_data_list: List[ItemData] = []
        instance_dict = self.model_dump(exclude={"cj_href"}, by_alias=True, mode='python')

        for field_name, field_info in self.model_fields.items():
            json_extra = field_info.json_schema_extra or {}
            if json_extra.get("cj_internal") or field_name == "cj_href":
                continue

            # Use alias if present for key in instance_dict, otherwise field_name
            dict_key = field_info.alias or field_name
            value = instance_dict.get(dict_key)
            prompt = field_info.title or field_name.replace('_', ' ').capitalize()

            id_dict: Dict[str, Any] = {
                "name": dict_key,  # Use alias for name in Cj
                "value": value,  # Pydantic model_dump handles serialization to Python types
                "prompt": prompt,
            }
            if json_extra.get("cj_type"): id_dict["type"] = json_extra["cj_type"]
            # Add other Cj item data metadata (e.g. render hints)
            for k, v in json_extra.items():
                if k.startswith("cj_item_attr_"):  # e.g. cj_item_attr_render
                    id_dict[k.replace("cj_item_attr_", "")] = v

            item_data_list.append(ItemData(**id_dict))
        return item_data_list

    def get_cj_instance_item_links(self, base_url: str = "") -> List[Link]:
        """Generates instance-specific links (e.g., edit, delete)."""
        links: List[Link] = []
        resolved_cj_href = self._resolve_href(self.cj_href or "", base_url=base_url) if self.cj_href else None

        if resolved_cj_href:
            links.append(Link(rel="edit", href=resolved_cj_href, prompt=f"Edit {self.__class__.__name__}",
                              method="GET"))  # GET to fetch edit form/data
            links.append(
                Link(rel="delete", href=resolved_cj_href, prompt=f"Delete {self.__class__.__name__}", method="DELETE"))
        return links

    def to_cj_item(self, context: Optional[Dict[str, Any]] = None) -> Item:
        base_url = self._get_base_url_from_context(context)
        item_rel_from_config = (self.model_config or {}).get("cj_item_rel", self.__class__.cj_item_rel)

        resolved_cj_href = self._resolve_href(self.cj_href or "", base_url=base_url) if self.cj_href else \
            self._resolve_href(self.__class__.cj_item_href_template.format(id="undefined"), base_url=base_url)

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
        """
        Generates the top-level CollectionJson Pydantic model.
        'instances' can be a single model instance or a list of them.
        'context' should contain 'base_url'.
        """
        base_url = cls._get_base_url_from_context(context)

        # Prepare collection_href
        collection_href = cls._resolve_href(cls.cj_collection_href_template, base_url=base_url)

        # Prepare global links and queries, resolving hrefs
        global_links = [
            Link(**{**link_def, "href": cls._resolve_href(link_def["href"], base_url=base_url)})
            for link_def in (collection_links_override or cls.cj_global_links)
        ]
        global_queries = [
            Query(**{**query_def, "href": cls._resolve_href(query_def["href"], base_url=base_url)})
            for query_def in (collection_queries_override or cls.cj_global_queries)
        ]

        items_list: List[Item] = []
        if instances:
            if isinstance(instances, list):
                items_list = [inst.to_cj_item(context=context) for inst in instances if isinstance(inst, cls)]
            elif isinstance(instances, cls):  # Single instance
                items_list = [instances.to_cj_item(context=context)]

        collection_obj = Collection(
            version=cls.cj_version,
            href=collection_href,
            title=collection_title_override or cls.cj_collection_title,
            links=global_links,
            items=items_list,
            queries=global_queries
        )

        template_obj = cls.get_cj_write_template(context=context)

        return CollectionJson(
            collection=collection_obj,
            template=template_obj,
            error=error_details
        )
