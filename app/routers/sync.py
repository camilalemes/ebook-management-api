import datetime
import logging
from typing import Dict, Any
from fastapi import APIRouter, Query, BackgroundTasks
from pydantic import BaseModel

from ..services.sync_service import sync_folders, get_sync_service

router = APIRouter(prefix="/sync", tags=["sync"])
logger = logging.getLogger(__name__)

# Keep track of sync status
sync_status = {
    "last_sync": None,
    "in_progress": False,
    "result": None,
    "errors": None
}


class SyncResponse(BaseModel):
    status: str
    last_sync: datetime.datetime | None = None
    details: Dict[str, Any] | None = None


def perform_sync(dry_run: bool = False):
    global sync_status

    try:
        sync_status["in_progress"] = True
        sync_status["result"] = None
        sync_status["errors"] = None

        # Get the sync service and run the sync
        sync_service = get_sync_service()
        result = sync_folders(dry_run=dry_run)

        logger.info(f"Sync completed. Result: {result}")
        sync_status["result"] = result
        sync_status["last_sync"] = datetime.datetime.now()
    except Exception as e:
        logger.error(f"Error during sync: {str(e)}")
        logger.exception(e)
        sync_status["errors"] = str(e)
    finally:
        sync_status["in_progress"] = False


@router.post("/trigger", response_model=SyncResponse)
async def trigger_sync(
        background_tasks: BackgroundTasks,
        dry_run: bool = Query(False, description="Run in dry-run mode without making changes")
):
    if sync_status["in_progress"]:
        return SyncResponse(
            status="already_running",
            last_sync=sync_status["last_sync"]
        )

    background_tasks.add_task(perform_sync, dry_run=dry_run)

    return SyncResponse(
        status="started",
        last_sync=sync_status["last_sync"]
    )

@router.get("/status", response_model=SyncResponse)
async def get_sync_status():
    """Get the current sync status"""
    return SyncResponse(
        status="in_progress" if sync_status["in_progress"] else "idle",
        last_sync=sync_status["last_sync"],
        details={
            "result": sync_status["result"],
            "errors": sync_status["errors"]
        }
    )