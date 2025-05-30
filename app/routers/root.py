from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from app.core.security import AuthenticatedUser, get_current_user
from app.dependencies import get_html_renderer
from app.core.html_renderer import HtmlRendererInterface

router = APIRouter()

@router.get("/", response_class=HTMLResponse)
async def read_root(
        request: Request,
        current_user: AuthenticatedUser | None = Depends(get_current_user),
        renderer: HtmlRendererInterface = Depends(get_html_renderer)
):
    """Serves the homepage."""
    if isinstance(current_user, RedirectResponse):
        return current_user
    return await renderer.render(
        "index.html",
        request,
        {"current_user": current_user}
    )
