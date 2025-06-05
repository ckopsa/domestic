from fastapi import Request, Header, status
from fastapi.responses import RedirectResponse
from typing import Optional, Dict, Any

from core.html_renderer import HtmlRendererInterface # Assuming HtmlRendererInterface is in src/core/

async def render_cj_response(
    request: Request,
    data: Dict[str, Any], # This is CollectionJson.model_dump() or an error dict
    template_name: str, # e.g., "items.html", "form.html", "error.html"
    html_renderer: HtmlRendererInterface,
    accept: Optional[str] = Header(None),
    status_code: int = status.HTTP_200_OK,
):
    if accept and "text/html" in accept.lower() and not "application/json" in accept.lower():
        # Handle HTML redirection for 201 CREATED or 200 OK on PUT (successful form submissions)
        if status_code == status.HTTP_201_CREATED or \
           (status_code == status.HTTP_200_OK and request.method == "PUT"):

            # Attempt to extract item URL from Collection+JSON structure for redirection
            # Assumes the 'data' dict is a CollectionJson model dump
            # and the first item's href is the target URL.
            item_url = None
            if data.get("collection") and data["collection"].get("items") and \
               isinstance(data["collection"]["items"], list) and len(data["collection"]["items"]) > 0:

                # Ensure items[0] is a dict and has 'href'
                first_item = data["collection"]["items"][0]
                if isinstance(first_item, dict):
                    item_url = first_item.get("href")

            if item_url:
                # Ensure URL is absolute or correctly relative for RedirectResponse
                # TestClient might need full URLs, live server might be fine with relative paths.
                # If item_url is already absolute, request.base_url parts won't be used.
                if not item_url.startswith(("http://", "https://")) and hasattr(request.base_url, "_url"):
                    # Construct absolute URL from base_url and item_url path
                    # item_url is expected to be a path like /cj/resource/id/
                    item_url = str(request.base_url.replace(path=item_url.lstrip('/')))


                return RedirectResponse(url=item_url, status_code=status.HTTP_303_SEE_OTHER)

        # For standard HTML rendering (GET requests or errors shown on a page)
        # The template should be able to handle the 'data' dict (e.g. if data.collection.error exists)
        return html_renderer.render_template(
            f"cj/{template_name}", # Assumes templates are in a 'cj/' subdirectory
            {"request": request, "data": data},
            status_code=status_code
        )
    else: # Default to JSON response
        # If 'data' represents a C+J error structure for a JSON response,
        # ensure the response status code matches the error code.
        if "collection" in data and "error" in data["collection"] and \
           isinstance(data["collection"]["error"], dict) and "code" in data["collection"]["error"]:

            error_status_code = data["collection"]["error"]["code"]
            # This part is tricky: FastAPI sets status_code primarily from decorator or direct Response.
            # To return a JSON response with a specific error code not raised via HTTPException,
            # one would typically return a JSONResponse(content=data, status_code=error_status_code).
            # However, this helper is designed to return the data dict itself for FastAPI to wrap.
            # If error_status_code is different from the endpoint's default (status_code param),
            # this won't automatically adjust. Best practice for JSON errors is to raise HTTPException.
            # For now, we assume the caller (endpoint) handles setting the correct status_code
            # for JSON error responses if not raising HTTPException.
            # This function will just return the data.
            # A common pattern is to raise HTTPException(status_code=error_status_code, detail=data)
            # from the endpoint itself for JSON errors.

        # Return the data dictionary; FastAPI will handle JSON serialization.
        # The status_code from the endpoint's decorator will be used unless overridden
        # by returning a Response object directly from the endpoint.
        return data
