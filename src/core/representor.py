from fastapi import Request
from fastapi.responses import JSONResponse

import cj_models
from core.html_renderer import HtmlRendererInterface


import datetime
from typing import Any


class Representor:
    def __init__(
            self,
            request: Request,
            html_renderer: HtmlRendererInterface,
    ):
        self.request = request
        self.html_renderer = html_renderer

    def _json_serializable_dict(self, data: Any) -> Any:
        if isinstance(data, datetime.datetime):
            return data.isoformat()
        if isinstance(data, datetime.date):
            return data.isoformat()
        if isinstance(data, dict):
            return {k: self._json_serializable_dict(v) for k, v in data.items()}
        if isinstance(data, list):
            return [self._json_serializable_dict(elem) for elem in data]
        return data

    async def represent(self, collection_json: cj_models.CollectionJson):
        accept_preferences = self.request.headers.get("Accept", "")
        accept_preferences = accept_preferences.split(",")
        for item in accept_preferences:
            match item.strip():
                case "application/vnd.collection+json":
                    return JSONResponse(
                        content=self._json_serializable_dict(collection_json.model_dump()),
                        headers={"Content-Type": "application/vnd.collection+json"}
                    )
                case _:
                    return JSONResponse(
                        content=self._json_serializable_dict(collection_json.model_dump()),
                        headers={"Content-Type": "application/vnd.collection+json"}
                    )
        return await self.html_renderer.render("cj_template.html", self.request,
                                               {"collection": collection_json.collection, "request": self.request,
                                                "template": collection_json.template, })
