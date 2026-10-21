import asyncio
from datetime import datetime, timezone
import logging
from typing import Any, Callable, Coroutine, Dict, List, Optional
import uuid
from pydantic import BaseModel, Field

from lifeos.shared.db.mongo import MongoDB

logger = logging.getLogger("lifeos.scheduler")


class ScheduleJob(BaseModel):
    id: str = Field(default_factory=lambda: f"sched_{uuid.uuid4().hex[:8]}")
    command: str
    interval_seconds: int = 3600  # Default 1 hour
    enabled: bool = True
    last_run_at: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class WorkflowScheduler:
    """Async background scheduler for recurring LifeOS natural-language operations."""

    def __init__(self, executor: Optional[Callable[[str], Coroutine[Any, Any, Any]]] = None):
        self.executor = executor
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._memory_jobs: Dict[str, ScheduleJob] = {}

    async def add_job(self, command: str, interval_seconds: int = 3600) -> ScheduleJob:
        job = ScheduleJob(command=command, interval_seconds=interval_seconds)
        try:
            db = MongoDB.get_database()
            await db.schedules.insert_one(job.model_dump())
        except Exception:
            self._memory_jobs[job.id] = job
        return job

    async def list_jobs(self) -> List[ScheduleJob]:
        try:
            db = MongoDB.get_database()
            cursor = db.schedules.find({}, {"_id": 0})
            docs = await cursor.to_list(length=100)
            return [ScheduleJob.model_validate(d) for d in docs]
        except Exception:
            return list(self._memory_jobs.values())

    async def remove_job(self, job_id: str) -> bool:
        try:
            db = MongoDB.get_database()
            res = await db.schedules.delete_one({"id": job_id})
            return res.deleted_count > 0
        except Exception:
            return self._memory_jobs.pop(job_id, None) is not None

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _loop(self) -> None:
        while self._running:
            try:
                jobs = await self.list_jobs()
                now = datetime.now(timezone.utc)
                for job in jobs:
                    if not job.enabled:
                        continue
                    should_run = False
                    if not job.last_run_at:
                        should_run = True
                    else:
                        last = datetime.fromisoformat(job.last_run_at)
                        if (now - last).total_seconds() >= job.interval_seconds:
                            should_run = True

                    if should_run and self.executor:
                        logger.info(f"Executing scheduled job {job.id}: '{job.command}'")
                        try:
                            await self.executor(job.command)
                            job.last_run_at = now.isoformat()
                            try:
                                db = MongoDB.get_database()
                                await db.schedules.update_one(
                                    {"id": job.id},
                                    {"$set": {"last_run_at": job.last_run_at}}
                                )
                            except Exception:
                                self._memory_jobs[job.id] = job
                        except Exception as e:
                            logger.error(f"Error executing scheduled job {job.id}: {e}")

                await asyncio.sleep(5)  # Tick interval
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Scheduler tick error: {e}")
                await asyncio.sleep(5)
