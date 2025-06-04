import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any, Type

from pydantic import BaseModel
from pydantic.fields import FieldInfo

from cj_models import Link, TemplateData, ItemData, Item, Template


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
        item_href = f"{self.base_api_url}/{resource_name}/{getattr(instance, 'id', uuid.uuid4().hex)}"
        data_list = self.item_data_converter.convert(instance)

        item_links = [Link(rel="self", href=item_href, prompt="View this resource", method="GET")]
        if hasattr(instance, "item_links"):  # This will find the method on the instance (from mixin or direct)
            item_links.extend(instance.item_links(self.base_api_url, resource_name))
        if additional_links: item_links.extend(additional_links)
        return Item(href=item_href, data=data_list, links=item_links)

    def create_template(self, pydantic_model_class: Type[BaseModel]) -> Template:
        template_data_list = self.template_data_converter.convert(pydantic_model_class)
        return Template(data=template_data_list)
