from __future__ import annotations

from typing import Optional, List

from pydantic import BaseModel, Field


class CollectionJson(BaseModel):
    collection: Collection
    template: Optional[Template] = Field(None, description="Template for the collection")
    error: Optional[Error] = Field(None, description="Error details, if any")


class Collection(BaseModel):
    version: str = "1.0"
    href: str
    links: List[Link] = Field(default_factory=list)
    items: List[Item] = Field(default_factory=list)
    queries: List[Query] = Field(default_factory=list)


class Error(BaseModel):
    title: str
    code: int
    message: str
    details: Optional[str] = None


class Template(BaseModel):
    data: List[TemplateData] = Field(default_factory=list)


class ItemData(BaseModel):
    name: str
    value: Optional[str | bool | int | float | dict | list] = Field(None, description="Value of the data item")
    prompt: Optional[str] = Field(None, description="Human Readable prompt for the data")
    type: Optional[str] = Field(None, description="Type of the data", examples=["text", "number", "boolean"])


class QueryData(ItemData):
    pass


class TemplateData(QueryData):
    required: Optional[bool] = False  # Indicates if this field is required in the template


class Query(BaseModel):
    rel: str
    href: str
    prompt: Optional[str] = None
    name: Optional[str] = None
    data: List[QueryData] = Field(default_factory=list)


class Item(BaseModel):
    href: str
    data: List[ItemData] = Field(default_factory=list)
    links: List[Link] = Field(default_factory=list)


class Link(BaseModel):
    rel: str
    href: str
    prompt: Optional[str] = None
    render: Optional[str] = None  # e.g., "link", "image", "text"
    media_type: Optional[str] = None  # e.g., "application/json", "text/html"
    method: Optional[str] = Field("GET", description="HTTP method for the link",
                                  examples=["GET", "POST", "PUT", "DELETE"])
