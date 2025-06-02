# main.py
import os
import sys

# Add the project root to sys.path to ensure 'app' module can be found
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.routers import root, workflow_definitions, workflow_instances, tasks, auth, user_workflows, api

app = FastAPI(
    redirect_slashes=False,
)

# Mount static files
app.mount("/static", StaticFiles(directory="app/templates"), name="static")

# Include routers
app.include_router(root.router)
app.include_router(workflow_definitions.router)
app.include_router(workflow_instances.router)
app.include_router(tasks.router)
app.include_router(auth.router)
app.include_router(user_workflows.router)
app.include_router(api.router)
