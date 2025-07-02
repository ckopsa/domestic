from fastapi import Request
from fastapi.responses import JSONResponse

import cj_models
from core.html_renderer import HtmlRendererInterface


class Representor:
    def __init__(
            self,
            request: Request,
            html_renderer: HtmlRendererInterface,
    ):
        self.request = request
        self.html_renderer = html_renderer

    async def represent(self, collection_json: cj_models.CollectionJson):
        accept_preferences = self.request.headers.get("Accept", "")
        accept_preferences = accept_preferences.split(",")
        for item in accept_preferences:
            match item.strip():
                case "application/vnd.collection+json":
                    return JSONResponse(
                        content=collection_json.dict(),
                        headers={"Content-Type": "application/vnd.collection+json"}
                    )
        return await self.html_renderer.render("cj_template.html", self.request,
                                               {"collection": collection_json.collection, "request": self.request,
                                                "template": collection_json.template, })
