from __future__ import annotations

import datetime
from typing import Optional, List, Union

import fastapi
from pydantic import BaseModel, Field as PydanticField

from transitions import TransitionManager


class Link(BaseModel):
    rel: str
    href: str
    prompt: Optional[str] = None
    render: Optional[str] = None
    media_type: Optional[str] = None
    method: Optional[str] = PydanticField("GET", description="HTTP method for the link")


class ItemData(BaseModel):
    name: str
    value: Union[str, bool, int, float, dict, list, None, datetime.datetime, datetime.date] = PydanticField(None,
                                                                                                            description="Value of the data item")
    prompt: Optional[str] = PydanticField(None, description="Human Readable prompt for the data")
    type: Optional[str] = PydanticField(None, description="Type of the data")
    input_type: Optional[str] = PydanticField(None,
                                              description="Suggested input type (e.g., 'text', 'checkbox', 'number', 'select')")
    options: Optional[List[str]] = PydanticField(None, description="List of options for 'select' input type")
    pattern: Optional[str] = PydanticField(None, description="Regex pattern for validation")
    min_length: Optional[int] = PydanticField(None, description="Minimum string length for validation")
    max_length: Optional[int] = PydanticField(None, description="Maximum string length for validation")
    minimum: Optional[Union[int, float]] = PydanticField(None, description="Minimum value for number range validation")
    maximum: Optional[Union[int, float]] = PydanticField(None, description="Maximum value for number range validation")
    render_hint: Optional[str] = PydanticField(None,
                                               description="A hint for how to render the data item (e.g., 'textarea', 'colorpicker')")


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
    href: Optional[str] = None
    method: Optional[str] = PydanticField("POST", description="HTTP method for the template")
    prompt: Optional[str] = None


class Error(BaseModel):
    title: str
    code: int
    message: str
    details: Optional[str] = None


class CollectionJson(BaseModel):
    collection: Collection
    template: Optional[List[Template]] = PydanticField(None, description="Templates for the collection")
    error: Optional[Error] = PydanticField(None, description="Error details, if any")


def to_collection_json_data(self: BaseModel, href="") -> Item:
    """
    Converts a Pydantic model instance into a Collection+JSON 'data' array.
    'self' will be the model instance when this is called.
    """
    schema = self.schema()
    model_dict = self.dict()
    cj_data = []

    for name, definition in schema.get("properties", {}).items():
        cj_data.append(ItemData(
            name=name,
            value=model_dict.get(name),
            prompt=definition.get("title") or name.replace("_", " ").title(),
            type=definition.get("type"),
            render_hint=definition.get("x-render-hint"),
        ))
    return Item(
        href=href,
        rel="item",
        data=cj_data
    )


BaseModel.to_cj_data = to_collection_json_data


class CollectionJsonRepresentor:
    def __init__(self, transition_manager: TransitionManager):
        self.transition_manager = transition_manager

    def to_collection_json(
            self,
            request: fastapi.Request,
            models: list[BaseModel],
            context: Optional[dict] = None,
            item_context_mapper: Optional[callable] = None
    ) -> CollectionJson:
        """
        Converts a list of Pydantic models into a Collection+JSON representation.
        """

        transitions = self.transition_manager.get_transitions(request)
        for transition in transitions:
            if transition.href:
                transition.href = transition.href.format(**context) if context else transition.href
        links = [transition.to_link() for transition in transitions if
                 not transition.properties and transition.method == 'GET']
        template = []
        for transition in [transition for transition in transitions if
                           transition.href and transition.method in ["POST", "PUT", "DELETE"]]:
            it_template = transition.to_template()
            if transition.href:
                it_template.href = transition.href
            else:
                it_template.href = str(request.url)
            if transition.method:
                it_template.method = transition.method

            template.append(it_template)

        items = []
        item_transitions = self.transition_manager.get_item_transitions(request)
        for item_model in models:
            item_links = []
            for transition in item_transitions:
                link_href = transition.href
                if item_context_mapper:
                    link_href = link_href.format(**item_context_mapper(item_model))
                if context:
                    link_href = link_href.format(**context)
                if not transition.properties:
                    link = transition.to_link()
                    link.href = link_href
                    item_links.append(link)

            item = item_model.to_cj_data(href="")
            item.links.extend(item_links)
            items.append(item)

        return CollectionJson(
            collection=Collection(
                href=str(request.url),
                version="1.0",
                items=items,
                queries=[],
                links=links,
                title="Title"
            ),
            template=template
        )
