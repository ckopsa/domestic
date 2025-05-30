from typing import List
from fastapi import Request, Depends
from fastapi.responses import HTMLResponse
from app.core.html_renderer import HtmlRendererInterface
from app.dependencies import get_html_renderer

async def create_message_page(
        request: Request,
        title: str,
        heading: str,
        message: str,
        links: List[tuple[str, str]],
        status_code: int = 200,
        renderer: HtmlRendererInterface = Depends(get_html_renderer)
) -> HTMLResponse:
    """Helper function to render simple HTML message pages using an abstracted renderer."""
    heading_style = "color: #48bb78;"
    if "error" in title.lower() or "fail" in title.lower():
        heading_style = "color: #ef4444;"
    elif "warn" in title.lower():
        heading_style = "color: #f6ad55;"
    
    response = await renderer.render(
        "message.html",
        request,
        {
            "title": title,
            "heading": heading,
            "message": message,
            "links": links,
            "heading_style": heading_style
        }
    )
    response.status_code = status_code
    return response
