from enum import Enum
from typing import Dict, Union
from typing import Optional, List

from fastapi import Request
from pydantic import BaseModel


class RelType(str, Enum):
    """Strongly-typed relation types for hypermedia links."""
    SELF = "self"
    COLLECTION = "collection"
    ITEM = "item"
    CREATE_FORM = "create-form"
    EDIT_FORM = "edit-form"
    APPROVE = "approve"
    REJECT = "reject"
    FILTER = "filter"


class FormProperty(BaseModel):
    name: str
    type: str
    prompt: str
    value: str | bool | int | float | None = None  # Allow multiple types
    required: bool = False
    input_type: Optional[str] = None
    options: Optional[List[str]] = None
    pattern: Optional[str] = None
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    minimum: Optional[Union[int, float]] = None
    maximum: Optional[Union[int, float]] = None
    render_hint: Optional[str] = None # example: hidden


class Form(BaseModel):
    id: str
    name: str
    href: str
    rel: str
    tags: str
    title: str
    method: str
    properties: list[dict]


class TransitionManager:
    """
    Manages hypermedia transitions by dynamically inspecting the FastAPI application's 
    OpenAPI schema. It organizes existing routes rather than redefining them.
    """

    def __init__(self):
        self.page_transitions: Dict[str, List[str]] = {}
        self.item_transitions: Dict[str, List[str]] = {}
        self.routes_info: Dict[str, Form] = {}

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

                params: List[FormProperty] = []
                for param in operation.get("parameters", []):
                    if param.get("in") == "path":
                        # params.append(param.get("name"))
                        pass
                    if param.get("in") == "query":
                        form_schema = param.get("schema", {})
                        if form_schema and "$ref" in form_schema:
                            schema_name = form_schema["$ref"].split('/')[-1]
                            form_schema = schema.get("components", {}).get("schemas", {}).get(schema_name, {})
                            enum_values = form_schema.get("enum")
                            schema_pattern = form_schema.get("pattern")
                            min_length = form_schema.get("minLength")
                            max_length = form_schema.get("maxLength")
                            minimum = form_schema.get("minimum")
                            maximum = form_schema.get("maximum")
                            schema_type = form_schema.get("type", "string")
                            render_hint = form_schema.get("x-render-hint")

                            # Determine input_type
                            input_type = schema_type  # Default
                            if schema_type == 'boolean':
                                input_type = 'checkbox'
                            elif schema_type == 'integer' or schema_type == 'number':
                                input_type = 'number'
                            elif schema_type == 'string' and enum_values:
                                input_type = 'select'
                            elif schema_type == 'string':
                                input_type = 'text'  # Explicitly 'text' for string

                            params.append(FormProperty(
                                name=param.get("name"),
                                value=form_schema.get("default") or "" if schema_type == "string" else props.get("default"),
                                type=schema_type,
                                required=param.get("required", False),
                                prompt=param.get("title") or param.get("name"),
                                input_type=input_type,
                                options=enum_values,
                                pattern=schema_pattern,
                                min_length=min_length,
                                max_length=max_length,
                                minimum=minimum,
                                maximum=maximum,
                                render_hint=render_hint,
                            ))
                        else:
                            params.append(FormProperty(
                                name=param.get("name"),
                                type=param.get("schema", {}).get("type", "string"),
                                required=param.get("required", False),
                                prompt=param.get("schema", {}).get("title", param.get("name")),
                                value=param.get("schema", {}).get("default", None),
                                render_hint=param.get("schema", {}).get("x-render-hint", None),
                            ))

                # From request body
                request_body = operation.get("requestBody")
                if request_body:
                    content = request_body.get("content", {})
                    if "application/json" in content:
                        pass # TODO Implement JSON schema extraction
                    elif "application/x-www-form-urlencoded" in content:
                        form_schema = content.get("application/x-www-form-urlencoded", {}).get("schema", {})
                        if form_schema:
                            if "$ref" in form_schema:
                                schema_name = form_schema["$ref"].split('/')[-1]
                                form_schema = schema.get("components", {}).get("schemas", {}).get(schema_name, {})
                                for name, props in form_schema.get("properties", {}).items():
                                    # Extract additional schema details
                                    enum_values = props.get("enum")
                                    schema_pattern = props.get("pattern")
                                    min_length = props.get("minLength")
                                    max_length = props.get("maxLength")
                                    minimum = props.get("minimum")
                                    maximum = props.get("maximum")
                                    schema_type = props.get("type", "string")
                                    render_hint = props.get("x-render-hint") # Extract render_hint

                                    # Determine input_type
                                    input_type = schema_type  # Default
                                    if schema_type == 'boolean':
                                        input_type = 'checkbox'
                                    elif schema_type == 'integer' or schema_type == 'number':
                                        input_type = 'number'
                                    elif schema_type == 'string' and enum_values:
                                        input_type = 'select'
                                    elif schema_type == 'string':
                                        input_type = 'text'  # Explicitly 'text' for string

                                    params.append(FormProperty(
                                        name=name,
                                        value=props.get("default") or "" if schema_type == "string" else props.get("default"),
                                        type=schema_type,
                                        required=name in form_schema.get("required", []),
                                        prompt=props.get("title", name),
                                        input_type=input_type,
                                        options=enum_values,
                                        pattern=schema_pattern,
                                        min_length=min_length,
                                        max_length=max_length,
                                        minimum=minimum,
                                        maximum=maximum,
                                        render_hint=render_hint, # Pass render_hint
                                    ))
                            else:
                                # params.extend(form_schema.get("properties", {}).keys())
                                pass
                            
                if method.upper() == 'GET' and len(params) > 0:
                    query_id = operation.get("operationId") + '_query'
                    self.routes_info[query_id] = Form(
                        id=query_id,
                        name=query_id,
                        href=path,
                        rel="",
                        tags=" ".join(operation.get("tags", [])),
                        title=operation.get("summary", ""),
                        method=method.upper(),
                        properties=[prop.dict() for prop in params],
                    )
                    self.page_transitions[operation.get("operationId")] = operation.get("pageTransitions", [])
                    self.item_transitions[operation.get("operationId")] = operation.get("itemTransitions", [])
                    self.routes_info[operation.get("operationId")] = Form(
                        id=operation.get("operationId"),
                        name=operation.get("operationId"),
                        href=path,
                        rel="",
                        tags=" ".join(operation.get("tags", [])),
                        title=operation.get("summary", ""),
                        method=method.upper(),
                        properties=[],
                    )
                else:
                    self.page_transitions[operation.get("operationId")] = operation.get("pageTransitions", [])
                    self.item_transitions[operation.get("operationId")] = operation.get("itemTransitions", [])
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

    def get_transitions(
            self,
            request: Request,
    ) -> List[Form]:
        """
        Get all valid transitions by filtering the app's known routes against the context.
        """
        self._load_routes_from_schema(request)
        forms_to_render: List[Form] = []
        function_name = request.scope.get('endpoint').__name__
        for transition_id in self.page_transitions.get(function_name, []):
            if transition_id not in self.routes_info:
                continue
            route_info = self.routes_info.get(transition_id)
            forms_to_render.append(route_info)
        return forms_to_render

    def get_item_transitions(
            self,
            request: Request,
    ) -> List[Form]:
        """
        Get item-specific transitions by filtering the app's known routes against the context.
        """
        self._load_routes_from_schema(request)
        forms_to_render: List[Form] = []
        function_name = request.scope.get('endpoint').__name__
        for transition_id in self.item_transitions.get(function_name, []):
            if transition_id not in self.routes_info:
                continue
            route_info = self.routes_info.get(transition_id)
            forms_to_render.append(route_info)
        return forms_to_render
