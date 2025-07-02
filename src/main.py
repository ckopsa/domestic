import os

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

# Treat src as a package
from src.routers import root, auth, workflow_definitions
from src.routers import workflow_instances as workflow_instances_router


def generate_unique_id(route: "APIRoute") -> str:
    operation_id = f"{route.name}"
    return operation_id


app = FastAPI(
    generate_unique_id_function=generate_unique_id
)

app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="*")

# Include routers
app.include_router(root.router)
app.include_router(auth.router)
app.include_router(workflow_definitions.router)
app.include_router(workflow_instances_router.router)
