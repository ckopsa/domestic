import os

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from routers import root, workflow_definitions, workflow_instances, tasks, auth, user_workflows, api, share
from routers.cj import workflow_definitions as cj_workflow_definitions_router
from routers.cj import workflow_instances as cj_workflow_instances_router
from routers.cj import task_instances as cj_task_instances_router

app = FastAPI(
    redirect_slashes=False,
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

# Include Collection+JSON routers
app.include_router(cj_workflow_definitions_router.router, prefix="/cj", tags=["Collection+JSON Workflows"])
app.include_router(cj_workflow_instances_router.router, prefix="/cj", tags=["Collection+JSON Workflow Instances"])
app.include_router(cj_task_instances_router.router, prefix="/cj", tags=["Collection+JSON Task Instances"])
