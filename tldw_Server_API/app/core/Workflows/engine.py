from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional

from loguru import logger

from tldw_Server_API.app.core.DB_Management.Workflows_DB import WorkflowsDatabase
from tldw_Server_API.app.core.Workflows.adapters import (
    run_prompt_adapter,
    run_rag_search_adapter,
    run_media_ingest_adapter,
    run_mcp_tool_adapter,
    run_webhook_adapter,
)


class RunMode(str, Enum):
    ASYNC = "async"
    SYNC = "sync"


@dataclass
class EngineConfig:
    tenant_id: str = "default"
    heartbeat_interval_sec: float = 2.0


class WorkflowEngine:
    """Minimal no-op engine that transitions runs through a simple lifecycle.

    This provides an anchor for API and state while the full step execution
    engine is being implemented per PRD v0.1.
    """

    def __init__(self, db: Optional[WorkflowsDatabase] = None, config: Optional[EngineConfig] = None):
        self.db = db or WorkflowsDatabase()
        self.config = config or EngineConfig()

    async def start_run(self, run_id: str, mode: RunMode = RunMode.ASYNC) -> None:
        """Execute a linear workflow with retries, timeouts, and cancel checks."""
        logger.info(f"WorkflowEngine: starting run {run_id} in mode={mode}")
        self.db.update_run_status(run_id, status="running", started_at=self._now_iso())
        self.db.append_event(self.config.tenant_id, run_id, "run_started", {"mode": mode})

        run = self.db.get_run(run_id)
        if not run:
            self.db.update_run_status(run_id, status="failed", status_reason="run_not_found", ended_at=self._now_iso())
            return

        # Load definition snapshot (always stored on run creation)
        try:
            import json
            definition = json.loads(run.definition_snapshot_json or "{}")
        except Exception:
            definition = {}

        steps = definition.get("steps") or []
        inputs = None
        try:
            import json as _json
            inputs = _json.loads(run.inputs_json or "{}")
        except Exception:
            inputs = {}

        # Shared context for templating
        context: Dict[str, Any] = {"inputs": inputs}
        last_outputs: Dict[str, Any] = {}

        try:
            # One-time orphan reaper pass before running
            await self._reap_orphans()

            for idx, step in enumerate(steps):
                step_id = step.get("id") or f"step_{idx+1}"
                step_name = step.get("name") or step_id
                step_type = (step.get("type") or "").strip()
                step_cfg = step.get("config") or {}

                self.db.append_event(self.config.tenant_id, run_id, "step_started", {"step_id": step_id, "type": step_type})
                step_run_id = f"{run_id}:{step_id}:{int(time.time()*1000)}"
                try:
                    self.db.create_step_run(
                        step_run_id=step_run_id,
                        run_id=run_id,
                        step_id=step_id,
                        name=step_name,
                        step_type=step_type,
                        status="running",
                        inputs={"config": step_cfg, "context_keys": list(context.keys())},
                    )
                    # Acquire lock and write initial heartbeat
                    self.db.update_step_lock_and_heartbeat(step_run_id=step_run_id, locked_by="engine", lock_ttl_seconds=int(self.config.heartbeat_interval_sec * 5))
                except Exception:
                    pass

                # Cancel check before running
                if self.db.is_cancel_requested(run_id):
                    self.db.update_run_status(run_id, status="cancelled", status_reason="cancelled_by_user", ended_at=self._now_iso())
                    self.db.append_event(self.config.tenant_id, run_id, "run_cancelled", {"by": "user", "before_step": step_id})
                    return

                # Execute with retries + timeout
                step_timeout = int(step.get("timeout_seconds") or 300)
                max_retries = int(step.get("retry") or 0)
                attempt = 0
                err: Optional[Exception] = None
                outputs: Dict[str, Any] = {}

                while attempt <= max_retries:
                    # Update heartbeat
                    try:
                        self.db.update_step_lock_and_heartbeat(step_run_id=step_run_id, locked_by="engine", lock_ttl_seconds=int(self.config.heartbeat_interval_sec * 5))
                    except Exception:
                        pass

                    attempt += 1
                    try:
                        outputs = await asyncio.wait_for(
                            self._run_step_adapter(step_type, step_cfg, context, last_outputs, run_id),
                            timeout=step_timeout,
                        )
                        err = None
                        break
                    except asyncio.TimeoutError as te:
                        err = te
                        self.db.append_event(self.config.tenant_id, run_id, "step_timeout", {"step_id": step_id, "attempt": attempt})
                    except Exception as e:
                        err = e

                    if attempt <= max_retries:
                        # Backoff with jitter
                        backoff = min(2 ** (attempt - 1), 8)
                        jitter = (0.25 + (0.5 * (time.time() % 1)))
                        await asyncio.sleep(backoff + jitter)

                # Final outcome
                if err:
                    # Failed step
                    self.db.append_event(self.config.tenant_id, run_id, "step_failed", {"step_id": step_id, "error": str(err)})
                    try:
                        self.db.complete_step_run(step_run_id=step_run_id, status="failed", outputs=outputs, error=str(err))
                    except Exception:
                        pass
                    self.db.update_run_status(run_id, status="failed", status_reason=str(err), ended_at=self._now_iso(), error=str(err))
                    self.db.append_event(self.config.tenant_id, run_id, "run_failed", {"error": str(err)})
                    return

                # Success path or waiting_human handled inside adapter helper
                last_outputs = outputs or {}
                context.update({"last": last_outputs})
                # If adapter returned special status
                if last_outputs.get("__status__") == "waiting_human":
                    try:
                        self.db.complete_step_run(step_run_id=step_run_id, status="waiting_human", outputs=last_outputs)
                    except Exception:
                        pass
                    return
                elif last_outputs.get("__status__") == "cancelled":
                    try:
                        self.db.complete_step_run(step_run_id=step_run_id, status="cancelled", outputs=last_outputs)
                    except Exception:
                        pass
                    self.db.update_run_status(run_id, status="cancelled", status_reason="cancelled_by_user", ended_at=self._now_iso())
                    self.db.append_event(self.config.tenant_id, run_id, "run_cancelled", {"by": "user", "during_step": step_id})
                    return

                self.db.append_event(self.config.tenant_id, run_id, "step_completed", {"step_id": step_id, "type": step_type})
                try:
                    self.db.complete_step_run(step_run_id=step_run_id, status="succeeded", outputs=last_outputs)
                except Exception:
                    pass

            # Complete run
            self.db.update_run_status(run_id, status="succeeded", ended_at=self._now_iso(), duration_ms=50, outputs=last_outputs)
            self.db.append_event(self.config.tenant_id, run_id, "run_completed", {"success": True})
            logger.info(f"WorkflowEngine: run {run_id} completed")
        except Exception as e:
            self.db.update_run_status(run_id, status="failed", status_reason=str(e), ended_at=self._now_iso(), error=str(e))
            self.db.append_event(self.config.tenant_id, run_id, "run_failed", {"error": str(e)})
            logger.error(f"WorkflowEngine: run {run_id} failed: {e}")

    async def continue_run(self, run_id: str, after_step_id: str, last_outputs: Optional[dict] = None) -> None:
        """Resume a run starting after the given step id (for human-in-loop)."""
        run = self.db.get_run(run_id)
        if not run:
            return

        try:
            import json
            definition = json.loads(run.definition_snapshot_json or "{}")
        except Exception:
            definition = {}
        steps = definition.get("steps") or []
        # Find next index
        start_idx = 0
        for i, s in enumerate(steps):
            if (s.get("id") or f"step_{i+1}") == after_step_id:
                start_idx = i + 1
                break
        context = {"inputs": json.loads(run.inputs_json or "{}")}
        if last_outputs:
            context["last"] = last_outputs
        # Mark running
        self.db.update_run_status(run_id, status="running", status_reason=None)
        self.db.append_event(self.config.tenant_id, run_id, "run_resumed", {"after": after_step_id})

        # Execute remaining steps
        temp_run_def = {"steps": steps[start_idx:]}
        # Temporarily reuse start_run logic by iterating here
        last = last_outputs or {}
        for idx, step in enumerate(steps[start_idx:], start=start_idx):
            sid = step.get("id") or f"step_{idx+1}"
            sname = step.get("name") or sid
            stype = (step.get("type") or "").strip()
            scfg = step.get("config") or {}
            self.db.append_event(self.config.tenant_id, run_id, "step_started", {"step_id": sid, "type": stype})
            step_run_id = f"{run_id}:{sid}:{int(time.time()*1000)}"
            try:
                self.db.create_step_run(step_run_id=step_run_id, run_id=run_id, step_id=sid, name=sname, step_type=stype, inputs={"config": scfg})
            except Exception:
                pass
            if stype == "prompt":
                out = await run_prompt_adapter(scfg, {**context, "prev": last})
            elif stype == "rag_search":
                out = await run_rag_search_adapter(scfg, {**context, "prev": last})
            elif stype == "media_ingest":
                out = await run_media_ingest_adapter(scfg, {**context, "prev": last})
            elif stype == "mcp_tool":
                out = await run_mcp_tool_adapter(scfg, {**context, "prev": last})
            elif stype == "webhook":
                out = await run_webhook_adapter(scfg, {**context, "prev": last})
            elif stype == "wait_for_human":
                self.db.update_run_status(run_id, status="waiting_human", status_reason="awaiting_review")
                try:
                    self.db.complete_step_run(step_run_id=step_run_id, status="waiting_human", outputs=last)
                except Exception:
                    pass
                return
            else:
                raise RuntimeError(f"Unsupported step type: {stype}")
            last = out or {}
            context.update({"last": last})
            self.db.append_event(self.config.tenant_id, run_id, "step_completed", {"step_id": sid, "type": stype})
            try:
                self.db.complete_step_run(step_run_id=step_run_id, status="succeeded", outputs=last)
            except Exception:
                pass

        # Finished
        duration_ms = None
        try:
            if run.started_at:
                from datetime import datetime
                fmt = "%Y-%m-%dT%H:%M:%S"
                # allow microseconds if present
                try:
                    started = datetime.fromisoformat(run.started_at)
                except Exception:
                    started = datetime.strptime(run.started_at.split(".")[0], fmt)
                duration_ms = int((datetime.utcnow() - started).total_seconds() * 1000)
        except Exception:
            duration_ms = None
        self.db.update_run_status(run_id, status="succeeded", ended_at=self._now_iso(), duration_ms=duration_ms, outputs=last)
        self.db.append_event(self.config.tenant_id, run_id, "run_completed", {"success": True})

    def submit(self, run_id: str, mode: RunMode = RunMode.ASYNC) -> None:
        """Submit a run for execution. Async mode schedules a task, sync blocks."""
        if mode == RunMode.SYNC:
            # Run in caller's loop synchronously
            loop = asyncio.get_event_loop()
            loop.create_task(self.start_run(run_id, mode))
        else:
            loop = asyncio.get_event_loop()
            loop.create_task(self.start_run(run_id, mode))

    def pause(self, run_id: str) -> None:
        self.db.update_run_status(run_id, status="paused", status_reason="paused_by_user")
        self.db.append_event(self.config.tenant_id, run_id, "run_paused", {"by": "user"})

    def resume(self, run_id: str) -> None:
        self.db.update_run_status(run_id, status="running", status_reason=None)
        self.db.append_event(self.config.tenant_id, run_id, "run_resumed", {"by": "user"})

    def cancel(self, run_id: str) -> None:
        try:
            self.db.set_cancel_requested(run_id, True)
        except Exception:
            pass
        self.db.update_run_status(run_id, status="cancelled", status_reason="cancelled_by_user")
        self.db.append_event(self.config.tenant_id, run_id, "run_cancelled", {"by": "user"})

    @staticmethod
    def _now_iso() -> str:
        return __import__("datetime").datetime.utcnow().isoformat()

    async def _run_step_adapter(
        self,
        step_type: str,
        step_cfg: Dict[str, Any],
        context: Dict[str, Any],
        last_outputs: Dict[str, Any],
        run_id: str,
    ) -> Dict[str, Any]:
        """Dispatch to the proper adapter with cancel/heartbeat hooks in context."""
        # Inject helper hooks
        ctx = {**context, "prev": last_outputs}
        ctx["is_cancelled"] = lambda: self.db.is_cancel_requested(run_id)
        ctx["heartbeat"] = lambda: None  # Engine-level heartbeat already updated per attempt

        if step_type == "prompt":
            return await run_prompt_adapter(step_cfg, ctx)
        if step_type == "rag_search":
            return await run_rag_search_adapter(step_cfg, ctx)
        if step_type == "media_ingest":
            return await run_media_ingest_adapter(step_cfg, ctx)
        if step_type == "mcp_tool":
            return await run_mcp_tool_adapter(step_cfg, ctx)
        if step_type == "webhook":
            return await run_webhook_adapter(step_cfg, ctx)
        if step_type == "wait_for_human":
            # Mark run waiting, signal caller via special status
            self.db.update_run_status(run_id, status="waiting_human", status_reason="awaiting_review")
            self.db.append_event(self.config.tenant_id, run_id, "waiting_human", {})
            return {"__status__": "waiting_human"}
        raise RuntimeError(f"Unsupported step type: {step_type}
")

    async def _reap_orphans(self) -> None:
        """Single pass to mark long-stale running steps as failed (orphaned)."""
        try:
            from datetime import datetime, timedelta, timezone
            cutoff = datetime.utcnow().replace(tzinfo=timezone.utc) - timedelta(seconds=int(self.config.heartbeat_interval_sec * 15))
            stale = self.db.find_orphan_step_runs(cutoff.isoformat())
            for s in stale:
                sid = s.get("step_run_id")
                rid = s.get("run_id")
                try:
                    self.db.complete_step_run(step_run_id=str(sid), status="failed", error="orphan_reaped")
                except Exception:
                    pass
                self.db.update_run_status(str(rid), status="failed", status_reason="orphan_reaped", ended_at=self._now_iso())
                self.db.append_event(self.config.tenant_id, str(rid), "run_failed", {"status_reason": "orphan_reaped", "step_run_id": sid})
        except Exception as e:
            logger.warning(f"Orphan reaper failed: {e}")
