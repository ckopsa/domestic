from fastapi import APIRouter, status

router = APIRouter(prefix="/api", tags=["api"])


@router.get("/healthz", status_code=status.HTTP_200_OK)
async def healthcheck():
    """API endpoint for health check."""
    return {"status": "ok"}

