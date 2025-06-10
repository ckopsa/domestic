from enum import Enum
from typing import Dict
from typing import Optional, List

from fastapi import Request
from pydantic import BaseModel

import cj_models

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


# --- UPDATED: Hypermedia Control Models ---
class FormProperty(BaseModel):
    name: str
    type: str
    prompt: str
    value: str | bool | int | float | None = None  # Allow multiple types
    required: bool = False


class Form(BaseModel):
    id: str  # Changed from str
    name: str
    href: str
    rel: str  # This could also be an Enum, but is often a space-delimited list
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

    def to_template(self):
        template_data = []
        for prop in self.properties:
            template_data.append(cj_models.TemplateData(
                **prop
            ))
        return cj_models.Template(
            data=template_data,
            prompt=self.title,
        )


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

                # FastAPI operationId is typically 'route_name_path_method'
                # We extract the 'name' we provided in the decorator.
                route_name = op_id.split('_')[0]

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
                        pass # TODO Implement JSON schema extraction
                    elif "application/x-www-form-urlencoded" in content:
                        form_schema = content.get("application/x-www-form-urlencoded", {}).get("schema", {})
                        if form_schema:
                            if "$ref" in form_schema:
                                schema_name = form_schema["$ref"].split('/')[-1]
                                form_schema = schema.get("components", {}).get("schemas", {}).get(schema_name, {})
                                for name, props in form_schema.get("properties", {}).items():
                                    params.append(FormProperty(
                                        name=name,
                                        value=props.get("default") or "" if props.get("type", "string") == "string" else None,
                                        type=props.get("type", "string"),
                                        required=name in form_schema.get("required", []),
                                        prompt=props.get("title", name),
                                    ))
                            else:
                                # params.extend(form_schema.get("properties", {}).keys())
                                pass
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
