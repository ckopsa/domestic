import os

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from routers import root, workflow_definitions, workflow_instances, tasks, auth, user_workflows, api, share


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
app.include_router(workflow_definitions.router)
app.include_router(workflow_instances.router)
app.include_router(tasks.router)
app.include_router(auth.router)
app.include_router(user_workflows.router)
app.include_router(api.router)
app.include_router(share.router)
