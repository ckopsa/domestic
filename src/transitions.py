import datetime
import enum
from typing import Dict, Union
from typing import Optional, List

from fastapi import Request
from pydantic import BaseModel
from pydantic.types import StrictBool

import cj_models


class FormProperty(BaseModel):
    name: str
    type: str
    prompt: str
    value: Union[StrictBool, int, float, dict, list, None, datetime.datetime, datetime.date, str] = None
    required: bool = False
    input_type: Optional[str] = None
    options: Optional[List[str]] = None
    render_hint: Optional[str] = None


class Form(BaseModel):
    id: str
    name: str
    href: str
    rel: str
    tags: str
    title: str
    method: str
    properties: list[dict]

    def to_link(self):
        return cj_models.Link(
            rel=self.rel,
            href=self.href,
            prompt=self.title,
            method=self.method,
        )

    def to_query(self):
        return cj_models.Query(
            rel=self.rel,
            href=self.href,
            prompt=self.title,
            data=[cj_models.TemplateData(**prop) for prop in self.properties],
        )

    def to_template(self, defaults: Optional[Dict[str, Union[str, StrictBool, int, float, None]]] = None):
        template_data = []
        for prop in self.properties:
            default_value = defaults.get(prop['name']) if defaults else None
            if isinstance(default_value, enum.Enum):
                default_value = default_value.value
            if default_value:
                prop['value'] = default_value
            template_data.append(cj_models.TemplateData(
                **prop
            ))
        return cj_models.Template(
            name=self.name,
            data=template_data,
            prompt=self.title,
            href=self.href,
            method=self.method,
        )


class TransitionManager:
    """
    Manages hypermedia transitions by dynamically inspecting the FastAPI application's
    OpenAPI schema. It organizes existing routes rather than redefining them.
    """

    def __init__(self, request: Request):
        self.page_transitions: Dict[str, List[str]] = {}
        self.item_transitions: Dict[str, List[str]] = {}
        self.routes_info: Dict[str, Form] = {}
        self._load_routes_from_schema(request)

    def _load_routes_from_schema(self, request: Request):
        """
        Parses the OpenAPI schema to build an internal cache of route information.
        """
        if self.routes_info:
            return

        schema = request.app.openapi()
        for path, path_item in schema.get("paths", {}).items():
            for method, operation in path_item.items():
                op_id = operation.get("operationId")
                if not op_id:
                    continue

                # Extract parameters for form properties
                params: List[FormProperty] = []
                # From path e.g. /wip/{item_id}
                for param in operation.get("parameters", []):
                    if param.get("in") == "path":
                        # params.append(param.get("name"))
                        pass

                # From request body
                request_body = operation.get("requestBody")
                if request_body:
                    content = request_body.get("content", {})
                    if "application/json" in content:
                        json_schema = content.get("application/json", {}).get("schema", {})
                        if json_schema:
                            if "$ref" in json_schema:
                                schema_name = json_schema["$ref"].split('/')[-1]
                                json_schema = schema.get("components", {}).get("schemas", {}).get(schema_name, {})
                                for name, props in json_schema.get("properties", {}).items():
                                    # Extract additional schema details
                                    enum_values = props.get("enum")
                                    schema_type = props.get("type", "string")
                                    render_hint = props.get("x-render-hint")

                                    # extract enum values if available
                                    enumRef = props.get("allOf")
                                    if enumRef and isinstance(enumRef, list) and len(enumRef) > 0:
                                        enum_schema_name = enumRef[0].get("$ref", "").split('/')[-1]
                                        enum_props = schema.get("components", {}).get("schemas", {}).get(
                                            enum_schema_name, {})
                                        enum_values = enum_props.get("enum")
                                        schema_type = enum_props.get("type", schema_type)

                                    # Determine input_type
                                    input_type = schema_type  # Default
                                    if schema_type == 'boolean':
                                        input_type = 'checkbox'
                                    elif schema_type == 'integer' or schema_type == 'number':
                                        input_type = 'number'
                                    elif schema_type == 'string' and enum_values:
                                        input_type = 'select'
                                    elif schema_type == 'string':
                                        input_type = 'text'
                                    params.append(FormProperty(
                                        name=name,
                                        value=props.get("default", None),
                                        type=schema_type,
                                        required=name in json_schema.get("required", []),
                                        prompt=props.get("title", name),
                                        input_type=input_type,
                                        options=enum_values,
                                        render_hint=render_hint,
                                    ))
                            else:
                                pass
                    elif "application/x-www-form-urlencoded" in content:
                        form_schema = content.get("application/x-www-form-urlencoded", {}).get("schema", {})
                        if form_schema:
                            if "$ref" in form_schema:
                                schema_name = form_schema["$ref"].split('/')[-1]
                                form_schema = schema.get("components", {}).get("schemas", {}).get(schema_name, {})
                                for name, props in form_schema.get("properties", {}).items():
                                    # Extract additional schema details
                                    enum_values = props.get("enum")
                                    schema_type = props.get("type", "string")
                                    render_hint = props.get("x-render-hint")  # Extract render_hint

                                    # Determine input_type
                                    input_type = schema_type  # Default
                                    if schema_type == 'boolean':
                                        input_type = 'checkbox'
                                    elif schema_type == 'integer' or schema_type == 'number':
                                        input_type = 'number'
                                    elif schema_type == 'string' and enum_values:
                                        input_type = 'select'
                                    elif schema_type == 'string':
                                        input_type = 'text'

                                    params.append(FormProperty(
                                        name=name,
                                        value=props.get("default", None),
                                        type=schema_type,
                                        required=name in form_schema.get("required", []),
                                        prompt=props.get("title", name),
                                        input_type=input_type,
                                        options=enum_values,
                                        render_hint=render_hint,
                                    ))
                            else:
                                pass
                self.routes_info[operation.get("operationId")] = Form(
                    id=operation.get("operationId"),
                    name=operation.get("operationId"),
                    href=path,
                    rel="",
                    tags=" ".join(operation.get("tags", [])),
                    title=operation.get("summary", ""),
                    method=method.upper(),
                    properties=[prop.dict() for prop in params],
                )

    def get_transition(self, transition_name: str, context: Dict[str, str]) -> Optional[Form]:
        """
        Get a specific transition by its name.
        """
        form = self.routes_info.get(transition_name).copy(deep=True)
        form.href = form.href.format(**context)
        return form