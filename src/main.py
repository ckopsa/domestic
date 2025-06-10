import os

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from routers import root, auth


def generate_unique_id(route: "APIRoute") -> str:
    operation_id = f"{route.name}"
    return operation_id


app = FastAPI(
    generate_unique_id_function=generate_unique_id
)

app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="*")

# Mount static files
app.mount("/static", StaticFiles(directory=f"{os.path.dirname(os.path.abspath(__file__))}/templates"), name="static")

# Include routers
app.include_router(root.router)
app.include_router(auth.router)
