from abc import ABC, abstractmethod
from typing import Dict, Any
from fastapi.templating import Jinja2Templates
from fastapi.requests import Request

class HtmlRendererInterface(ABC):
    @abstractmethod
    async def render(self, template_name: str, request: Request, context: Dict[str, Any]) -> str:
        pass

class Jinja2HtmlRenderer(HtmlRendererInterface):
    def __init__(self, templates: Jinja2Templates):
        self.templates = templates

    async def render(self, template_name: str, request: Request, context: Dict[str, Any]) -> str:
        return self.templates.TemplateResponse(template_name, {"request": request, **context})
