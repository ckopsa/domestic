from __future__ import annotations

import datetime
from typing import Optional, List, Union

from pydantic import BaseModel, Field as PydanticField
from pydantic.types import StrictBool


class Link(BaseModel):
    rel: str
    href: str
    prompt: Optional[str] = None
    render: Optional[str] = None
    media_type: Optional[str] = None
    method: Optional[str] = PydanticField("GET", description="HTTP method for the link")


class ItemData(BaseModel):
    name: str
    value: Union[StrictBool, int, float, dict, list, None, datetime.datetime, datetime.date, str] = PydanticField(None,
                                                                                                                  description="Value of the data item")
    prompt: Optional[str] = PydanticField(None, description="Human Readable prompt for the data")
    type: Optional[str] = PydanticField(None, description="Type of the data")
    input_type: Optional[str] = PydanticField(None,
                                              description="Suggested input type (e.g., 'text', 'checkbox', 'number', 'select')")
    render_hint: Optional[str] = PydanticField(None,
                                               description="A hint for how to render the data item (e.g., 'textarea', 'colorpicker')")


class QueryData(ItemData):
    options: Optional[List[str]] = PydanticField(None, description="List of options for 'select' input type")


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
    name: str
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


def to_collection_json_data(self: BaseModel, href="", links=None) -> Item:
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
        data=cj_data,
        links=links or [],
    )


BaseModel.to_cj_data = to_collection_json_data
