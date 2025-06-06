from __future__ import annotations

from datetime import datetime
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
