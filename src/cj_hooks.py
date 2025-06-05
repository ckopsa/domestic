import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any, Type

from pydantic import BaseModel
from pydantic.fields import FieldInfo

from cj_models import Link, TemplateData, ItemData, Item, Template, CollectionJson, Collection, Error


class CJHooks:
    """
    A mixin providing default implementations for Collection+JSON customization hooks.
    Application Pydantic models can inherit from this to customize their C+J representation.
    """

    # Fields to explicitly include in Item.data, even if they are collection types
    # Override in subclasses if needed.
    _include_fields_in_data: List[str] = []

    # Fields to explicitly skip when generating a Template.data array
    # Override in subclasses if needed.
    _template_skip_fields: List[str] = ["id", "created_at", "share_token"]  # Common defaults

    def item_links(self, base_api_url: str, resource_name: str) -> List['Link']:
        """
        Returns a list of custom Link objects for an Item.
        Default: Returns an empty list.
        """
        return []

    # You can add classmethod hooks for template customization too
    @classmethod
    def template_field_override(cls, field_name: str, field_info: FieldInfo,
                                field_inspector: 'PydanticFieldInspector') -> Optional[List['TemplateData']]:
        """
        Allows a model to provide a completely custom TemplateData list for a specific field.
        If this returns a list, the default template data generation for this field is skipped.
        Default: Returns None (no override).
        """
        # Example: if field_name == "task_definitions": return cls._cj_template_task_definitions()
        return None


class PydanticFieldInspector:
    def get_prompt(self, field_info: FieldInfo, field_name: str) -> str:
        prompt = None
        if field_info.json_schema_extra and isinstance(field_info.json_schema_extra, dict):
            prompt = field_info.json_schema_extra.get("cj_prompt")
        if not prompt and field_info.description:
            prompt = field_info.description
        return prompt or field_name.replace("_", " ").title()

    def is_collection_type(self, field_info: FieldInfo) -> bool:
        origin_type = getattr(field_info.annotation, "__origin__", None)
        return origin_type in (list, List, dict, Dict)

    def get_value_representation(self, value: Any) -> Any:
        if isinstance(value, datetime): return value.isoformat()
        if isinstance(value, BaseModel): return value.model_dump()
        if isinstance(value, list) and value and all(isinstance(i, BaseModel) for i in value):
            return [i.model_dump() for i in value]
        return value
    
    def get_type_representation(self, value: Any, field_info: FieldInfo) -> str:
        annotation_type = field_info.annotation
        if annotation_type is not None and hasattr(annotation_type, "__name__"):
            match annotation_type.__name__:
                case "Optional" | "list":
                    if hasattr(annotation_type, "__args__") and annotation_type.__args__:
                        inner_type = annotation_type.__args__[0]
                        if inner_type is type(None):
                            value_type = "NoneType"
                        value_type = inner_type.__name__
                case _:
                    value_type = annotation_type.__name__
        elif hasattr(value, "__class__"):
            value_type = type(value).__name__
        else:
            value_type = type(value).__name__ if value is not None else "NoneType"
        match value_type:
            case "int" | "float":
                return "number"
            case "bool":
                return "boolean"
            case "dict":
                return "object"
            case "list":
                return "array"
            case "datetime":
                return "datetime"
            case "NoneType":
                return "null"
            case _:
                return "text"  # Default type for unrecognized types


class DataArrayStrategy:
    field_inspector: PydanticFieldInspector = PydanticFieldInspector()


class PydanticToTemplateDataArray(DataArrayStrategy):
    def convert(self, model_class: Type[BaseModel]) -> List[TemplateData]:
        template_data_list = []
        # Use skip_fields from the model class itself if it inherited from the mixin,
        # otherwise, use a hardcoded default (or make it a parameter).
        # For this example, we assume the model class might have _cj_template_skip_fields.
        default_skips = ["id", "created_at", "share_token"]  # Fallback if model doesn't define its own
        skip_fields = getattr(model_class, "_template_skip_fields", default_skips)

        for field_name, field_info in model_class.model_fields.items():
            if field_name in skip_fields:
                continue

            # OCP: Check for special handler method on the model class (from mixin or overridden)
            # This allows model-specific representation of a field in a template.
            if hasattr(model_class, "template_field_override"):
                custom_template_data = model_class.template_field_override(field_name, field_info, self.field_inspector)
                if custom_template_data is not None:
                    template_data_list.extend(custom_template_data)
                    continue

            prompt = self.field_inspector.get_prompt(field_info, field_name)
            is_required = field_info.is_required()

            template_data_list.append(
                TemplateData(name=field_name, value="", prompt=prompt, required=is_required,
                             type=self.field_inspector.get_type_representation(None, field_info))
            )
        return template_data_list


class PydanticToItemDataArray(DataArrayStrategy):
    def convert(self, instance: BaseModel, model_class_for_metadata: Optional[Type[BaseModel]] = None) -> List[
        ItemData]:
        data_list = []
        cls_for_metadata = model_class_for_metadata or instance.__class__
        # Use include_fields from the instance (potentially from mixin)
        include_fields = getattr(instance, "include_fields_in_data", [])

        for field_name, field_info in cls_for_metadata.model_fields.items():
            if self.field_inspector.is_collection_type(field_info) and field_name not in include_fields:
                continue

            if hasattr(instance, field_name):
                value = getattr(instance, field_name)
                prompt = self.field_inspector.get_prompt(field_info, field_name)
                processed_value = self.field_inspector.get_value_representation(value)
                data_list.append(
                    ItemData(name=field_name, value=processed_value, prompt=prompt,
                             type=self.field_inspector.get_type_representation(value, field_info)))
        return data_list


class CollectionJSONBuilder:
    def __init__(self, base_api_url: str,
                 item_data_strategy: PydanticToItemDataArray = PydanticToItemDataArray(),
                 template_data_strategy: PydanticToTemplateDataArray = PydanticToTemplateDataArray()):  # Query strategy removed for brevity
        self.base_api_url = base_api_url
        self.item_data_converter = item_data_strategy
        self.template_data_converter = template_data_strategy

    def create_item(self, instance: BaseModel, resource_name: str,
                    additional_links: Optional[List[Link]] = None) -> Item:
        # Ensure item_href ends with a slash
        item_id_part = getattr(instance, 'id', uuid.uuid4().hex)
        item_href = f"{self.base_api_url}/{resource_name}/{item_id_part}"
        if not item_href.endswith("/"):
            item_href += "/"
        data_list = self.item_data_converter.convert(instance)

        item_links = [Link(rel="self", href=item_href, prompt="View this resource", method="GET")]
        if hasattr(instance, "item_links"):  # This will find the method on the instance (from mixin or direct)
            item_links.extend(instance.item_links(self.base_api_url, resource_name))
        if additional_links: item_links.extend(additional_links)
        return Item(href=item_href, data=data_list, links=item_links)

    def create_template(self, pydantic_model_class: Type[BaseModel]) -> Template:
        template_data_list = self.template_data_converter.convert(pydantic_model_class)
        return Template(data=template_data_list)


def create_cj_item_response(
    instance: BaseModel,
    resource_name: str,
    base_api_url: str,
    builder: CollectionJSONBuilder,
    additional_links: Optional[List[Link]] = None
) -> CollectionJson:
    """
    Creates a Collection+JSON response for a single item.
    """
    item = builder.create_item(instance, resource_name, additional_links=additional_links) # item.href will now have trailing slash

    # Ensure collection_href (for context links) ends with a slash
    collection_context_href = f"{base_api_url}/{resource_name}"
    if not collection_context_href.endswith("/"):
        collection_context_href += "/"

    form_href = f"{collection_context_href}form/"

    collection_links = [
        Link(rel="up", href=base_api_url if base_api_url != "/" else "/", prompt="Back to API root"), # Avoid double slash for root
        Link(rel="self", href=collection_context_href, prompt=f"View all {resource_name}"),
        Link(rel="create", href=form_href, prompt=f"Create new {resource_name[:-1] if resource_name.endswith('s') else resource_name}", method="GET") # Simple singularize
    ]

    # Consider adding a template for the item type if appropriate, though often not for single item views
    # template = builder.create_template(instance.__class__)

    return CollectionJson(
        collection=Collection(
            version="1.0",
            href=item.href, # The href of the item itself for a single item "collection" view
            links=collection_links, # Links relevant to this item/context
            items=[item]
            # template=template # Optionally add template
        )
    )

def create_cj_collection_response(
    instances: List[BaseModel],
    model_class: Type[BaseModel], # Pass the Pydantic model class for template generation
    resource_name: str,
    base_api_url: str,
    builder: CollectionJSONBuilder,
    collection_links: Optional[List[Link]] = None,
    item_additional_links_callable: Optional[callable] = None # e.g., lambda item: [Link(...)]
) -> CollectionJson:
    """
    Creates a Collection+JSON response for a list of items.
    Includes a template for creating new items of this type.
    """
    items = [] # Items created by builder.create_item will have trailing slashes in their hrefs
    for instance in instances:
        additional_links_for_item = []
        if item_additional_links_callable:
            additional_links_for_item = item_additional_links_callable(instance)
        items.append(builder.create_item(instance, resource_name, additional_links=additional_links_for_item))

    # Ensure collection_href (for the collection itself) ends with a slash
    collection_self_href = f"{base_api_url}/{resource_name}"
    if not collection_self_href.endswith("/"):
        collection_self_href += "/"

    form_href = f"{collection_self_href}form/"

    default_collection_links = [
        Link(rel="up", href=base_api_url if base_api_url != "/" else "/", prompt="Back to API root"), # Avoid double slash for root
        Link(rel="self", href=collection_self_href, prompt=f"View all {resource_name}"),
        Link(rel="create", href=form_href, prompt=f"Create new {resource_name[:-1] if resource_name.endswith('s') else resource_name}", method="GET")
    ]
    if collection_links:
        default_collection_links.extend(collection_links)

    template = builder.create_template(model_class)

    return CollectionJson(
        collection=Collection(
            version="1.0",
            href=collection_self_href, # Use the slash-terminated href
            links=default_collection_links,
            items=items
            # template field removed from Collection model
        ),
        template=template # template is a sibling to collection in CollectionJson
    )

def create_cj_form_template_response(
    model_class: Type[BaseModel],
    resource_name: str,
    base_api_url: str,
    builder: CollectionJSONBuilder,
    item_instance: Optional[BaseModel] = None, # For pre-filling a form for an existing item
    form_purpose: str = "create" # "create" or "edit"
) -> CollectionJson:
    """
    Creates a Collection+JSON response containing a template for a form.
    If item_instance is provided, the template can be used for an edit form.
    """
    template = builder.create_template(model_class)

    # Ensure base collection_href for "up" link ends with a slash
    base_collection_href = f"{base_api_url}/{resource_name}"
    if not base_collection_href.endswith("/"):
        base_collection_href += "/"

    if item_instance:
        item_data_map = {data.name: data.value for data in builder.item_data_converter.convert(item_instance)}
        for td in template.data:
            if td.name in item_data_map:
                td.value = item_data_map[td.name]

        item_id_part = getattr(item_instance, 'id', '')
        # form_context_href is the specific item's URL, ending with a slash
        form_context_href = f"{base_collection_href}{item_id_part}"
        if item_id_part and not form_context_href.endswith("/"): # Ensure slash if ID is present
             form_context_href += "/"

        # self_form_href points to the form for this specific item
        self_form_href = f"{form_context_href}form/"
        submit_href = self_form_href # Submit to the form URL itself for PUT

        links = [
            Link(rel="up", href=base_collection_href, prompt=f"Back to {resource_name} list"),
            Link(rel="self", href=self_form_href, prompt=f"{form_purpose.capitalize()} {model_class.__name__}"),
            Link(rel="submit", href=submit_href, prompt="Submit Form", method="PUT")
        ]
    else: # Creation form
        # form_context_href is the general form URL for creation
        form_context_href = f"{base_collection_href}form/"
        links = [
            Link(rel="up", href=base_collection_href, prompt=f"Back to {resource_name} list"),
            Link(rel="self", href=form_context_href, prompt=f"Create new {model_class.__name__}"),
            Link(rel="submit", href=form_context_href, prompt="Submit Form", method="PUT") # Submit to the form URL for POST (or PUT if idempotent create)
        ]

    return CollectionJson(
        collection=Collection(
            version="1.0",
            href=form_context_href, # The href for the form itself
            links=links,
            items=[], # No items for a template-only response, unless it's an edit form showing the item
            template=template
        )
    )

def create_cj_error_response(
    title: str,
    status_code: int,
    message: str,
    href: str,
    details: Optional[str] = None
) -> CollectionJson:
    """
    Creates a Collection+JSON error response.
    """
    return CollectionJson(
        collection=Collection(
            version="1.0",
            href=href, # URL related to the error context
            error=Error(
                title=title,
                code=status_code,
                message=message,
                details=details
            )
        )
    )
