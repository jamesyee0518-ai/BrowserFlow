"""Workflow API routes — CRUD and execution endpoints."""

from __future__ import annotations

import logging
import os
import uuid
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from . import database as db
from .models import (
    WorkflowCreate,
    WorkflowResponse,
    WorkflowRunCreate,
    WorkflowRunResponse,
)
from .workflow_executor import WorkflowExecutor

logger = logging.getLogger("cloakbrowser.manager.workflow_api")

router = APIRouter(prefix="/api/workflows", tags=["workflows"])

_executor: WorkflowExecutor | None = None


def init_executor(executor: WorkflowExecutor) -> None:
    global _executor
    _executor = executor


def _get_executor() -> WorkflowExecutor:
    if _executor is None:
        raise HTTPException(status_code=503, detail="Workflow executor not initialized")
    return _executor


def _get_output_dir() -> Path:
    data_dir = os.environ.get("CLOAKBROWSER_DATA_DIR", "/data")
    return Path(data_dir) / "workflow_outputs"


@router.get("", response_model=list[WorkflowResponse])
async def list_workflows():
    return db.list_workflows()


@router.post("", response_model=WorkflowResponse, status_code=201)
async def create_workflow(req: WorkflowCreate):
    profile = db.get_profile(req.profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail=f"Profile {req.profile_id} not found")

    workflow = db.create_workflow(
        title=req.title,
        description=req.description,
        profile_id=req.profile_id,
        definition=req.definition,
        run_with=req.run_with,
        ai_fallback=req.ai_fallback,
        adaptive_caching=req.adaptive_caching,
        schedule=req.schedule,
    )
    return workflow


@router.get("/runs", response_model=list[WorkflowRunResponse])
async def list_workflow_runs(limit: int = 50, offset: int = 0):
    return db.list_workflow_runs(limit=limit, offset=offset)


@router.get("/runs/{run_id}", response_model=WorkflowRunResponse)
async def get_workflow_run(run_id: str):
    run = db.get_workflow_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Workflow run not found")
    return run


@router.get("/outputs")
async def list_output_files(subdir: str = ""):
    out_dir = _get_output_dir()
    if subdir:
        out_dir = out_dir / subdir
    if not out_dir.exists():
        return {"files": [], "total": 0}
    files = []
    for f in sorted(out_dir.rglob("*")):
        if f.is_file():
            rel = f.relative_to(_get_output_dir())
            stat = f.stat()
            files.append({
                "path": str(rel),
                "name": f.name,
                "size": stat.st_size,
                "modified": stat.st_mtime,
            })
    return {"files": files, "total": len(files)}


@router.get("/outputs/download/{file_path:path}")
async def download_output_file(file_path: str):
    out_dir = _get_output_dir()
    full_path = (out_dir / file_path).resolve()
    if not str(full_path).startswith(str(out_dir.resolve())):
        raise HTTPException(status_code=403, detail="Access denied")
    if not full_path.exists() or not full_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(
        path=str(full_path),
        filename=full_path.name,
        media_type="application/octet-stream",
    )


@router.get("/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(workflow_id: str):
    workflow = db.get_workflow(workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return workflow


@router.put("/{workflow_id}", response_model=WorkflowResponse)
async def update_workflow(workflow_id: str, req: WorkflowCreate):
    workflow = db.update_workflow(
        workflow_id,
        title=req.title,
        description=req.description,
        profile_id=req.profile_id,
        definition=req.definition,
        run_with=req.run_with,
        ai_fallback=req.ai_fallback,
        adaptive_caching=req.adaptive_caching,
        schedule=req.schedule,
    )
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return workflow


@router.delete("/{workflow_id}", status_code=204)
async def delete_workflow(workflow_id: str):
    if not db.delete_workflow(workflow_id):
        raise HTTPException(status_code=404, detail="Workflow not found")


@router.post("/{workflow_id}/run", response_model=WorkflowRunResponse)
async def run_workflow(workflow_id: str, req: WorkflowRunCreate | None = None):
    workflow = db.get_workflow(workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    if workflow.get("status") == "running":
        raise HTTPException(status_code=409, detail="Workflow is already running")

    run_id = str(uuid.uuid4())
    parameters = req.parameters if req else None

    db.create_workflow_run(
        run_id=run_id,
        workflow_id=workflow_id,
        profile_id=workflow["profile_id"],
        parameters=parameters,
    )
    db.update_workflow(workflow_id, status="running")

    executor = _get_executor()

    try:
        result = await executor.execute_workflow(
            workflow=workflow,
            workflow_run_id=run_id,
            parameters=parameters,
        )
    except Exception as e:
        logger.error("Workflow execution failed: %s", e)
        db.update_workflow_run(run_id, status="failed", error=str(e))
        db.update_workflow(workflow_id, status="failed")
        raise HTTPException(status_code=500, detail=f"Workflow execution failed: {e}")

    db.update_workflow_run(
        run_id,
        status=result.status,
        execution_path=result.execution_path,
        blocks_completed=result.blocks_completed,
        blocks_total=result.blocks_total,
        llm_tokens_used=result.llm_tokens_used,
        duration_seconds=result.duration_seconds,
        output=result.output,
        error=result.error,
    )

    if result.status == "completed" and workflow.get("definition"):
        definition = workflow["definition"]
        has_cached = any(
            b.get("cached_script") for b in definition.get("blocks", [])
        )
        if has_cached:
            db.update_workflow(workflow_id, definition=definition)

    db.update_workflow(workflow_id, status="completed" if result.status == "completed" else "failed")

    return WorkflowRunResponse(
        workflow_run_id=result.workflow_run_id,
        workflow_id=result.workflow_id,
        profile_id=result.profile_id,
        status=result.status,
        execution_path=result.execution_path,
        blocks_completed=result.blocks_completed,
        blocks_total=result.blocks_total,
        llm_tokens_used=result.llm_tokens_used,
        duration_seconds=result.duration_seconds,
        output=result.output,
        error=result.error,
    )


@router.get("/{workflow_id}/outputs")
async def list_workflow_output_files(workflow_id: str):
    workflow = db.get_workflow(workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    out_dir = _get_output_dir() / workflow_id
    if not out_dir.exists():
        return {"files": [], "total": 0, "workflow_id": workflow_id}
    files = []
    for f in sorted(out_dir.rglob("*")):
        if f.is_file():
            rel = f.relative_to(out_dir)
            stat = f.stat()
            files.append({
                "path": str(rel),
                "name": f.name,
                "size": stat.st_size,
                "modified": stat.st_mtime,
            })
    return {"files": files, "total": len(files), "workflow_id": workflow_id}
