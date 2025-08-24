"""
In-memory job queue and task distribution system.
Manages job scheduling, worker allocation, and queue monitoring.
"""

import asyncio
import threading
from typing import Dict, List, Optional, Set
from dataclasses import dataclass
from datetime import datetime, timedelta
import time

from src.storage.memory_store import (
    get_memory_store, JobStatus, JobPriority, ExecutionStrategy, QueueStats
)
from src.orchestration.async_engine_memory import AsyncOrchestrationEngine
from src.utils.logging_config import get_logger

logger = get_logger()

@dataclass
class WorkerInfo:
    """Information about a worker"""
    worker_id: str
    is_active: bool = True
    current_job_id: Optional[str] = None
    jobs_processed: int = 0
    last_activity: datetime = None
    
    def __post_init__(self):
        if self.last_activity is None:
            self.last_activity = datetime.now()

class JobQueueMemory:
    """In-memory job queue with priority scheduling and worker management"""
    
    def __init__(self, max_concurrent_jobs: int = 3):
        self.max_concurrent_jobs = max_concurrent_jobs
        self.workers: Dict[str, WorkerInfo] = {}
        self.is_running = False
        self.memory_store = get_memory_store()
        self.orchestration_engine = AsyncOrchestrationEngine()
        self._lock = asyncio.Lock()
        self._worker_counter = 0
        
    async def start(self):
        """Start the job queue processing"""
        if self.is_running:
            return
        
        self.is_running = True
        logger.info("Job queue started")
        
        # Start worker management task
        asyncio.create_task(self._worker_manager())
        
        # Start queue processing task
        asyncio.create_task(self._process_queue())
        
    async def stop(self):
        """Stop the job queue processing"""
        self.is_running = False
        
        # Wait for all workers to finish
        while any(worker.is_active and worker.current_job_id for worker in self.workers.values()):
            await asyncio.sleep(0.1)
        
        logger.info("Job queue stopped")
    
    async def _worker_manager(self):
        """Manage worker lifecycle and allocation"""
        while self.is_running:
            try:
                async with self._lock:
                    # Clean up inactive workers
                    current_time = datetime.now()
                    inactive_workers = []
                    
                    for worker_id, worker in self.workers.items():
                        if (worker.current_job_id is None and 
                            current_time - worker.last_activity > timedelta(minutes=5)):
                            inactive_workers.append(worker_id)
                    
                    for worker_id in inactive_workers:
                        del self.workers[worker_id]
                        logger.debug(f"Removed inactive worker: {worker_id}")
                
                await asyncio.sleep(10)  # Check every 10 seconds
                
            except Exception as e:
                logger.error(f"Error in worker manager: {str(e)}")
                await asyncio.sleep(5)
    
    async def _process_queue(self):
        """Main queue processing loop"""
        while self.is_running:
            try:
                # Check if we can process more jobs
                active_workers = len([w for w in self.workers.values() 
                                    if w.is_active and w.current_job_id])
                
                if active_workers < self.max_concurrent_jobs:
                    # Get next job from queue
                    job_id = self.memory_store.dequeue_job()
                    
                    if job_id:
                        # Create worker for this job
                        worker_id = await self._create_worker()
                        
                        # Assign job to worker
                        await self._assign_job_to_worker(worker_id, job_id)
                        
                        # Start job processing
                        asyncio.create_task(self._process_job(worker_id, job_id))
                
                await asyncio.sleep(1)  # Check queue every second
                
            except Exception as e:
                logger.error(f"Error in queue processing: {str(e)}")
                await asyncio.sleep(5)
    
    async def _create_worker(self) -> str:
        """Create a new worker"""
        async with self._lock:
            self._worker_counter += 1
            worker_id = f"worker_{self._worker_counter}"
            
            self.workers[worker_id] = WorkerInfo(
                worker_id=worker_id,
                is_active=True,
                last_activity=datetime.now()
            )
            
            logger.debug(f"Created worker: {worker_id}")
            return worker_id
    
    async def _assign_job_to_worker(self, worker_id: str, job_id: str):
        """Assign a job to a worker"""
        async with self._lock:
            if worker_id in self.workers:
                self.workers[worker_id].current_job_id = job_id
                self.workers[worker_id].last_activity = datetime.now()
                
                # Mark job as running in memory store
                self.memory_store.mark_job_running(job_id, worker_id)
                
                logger.info(f"Assigned job {job_id} to worker {worker_id}")
    
    async def _process_job(self, worker_id: str, job_id: str):
        """Process a single job"""
        try:
            logger.info(f"Worker {worker_id} starting job {job_id}")
            
            # Get job details
            job = self.memory_store.get_job(job_id)
            if not job:
                logger.error(f"Job {job_id} not found")
                return
            
            # Add progress event
            self.memory_store.add_progress_event(
                job_id=job_id,
                event_type="job_started",
                message=f"Job started by worker {worker_id}",
                progress_percentage=5.0
            )
            
            # Update job phase
            job.current_phase = "extracting_data"
            self.memory_store.update_job(job)
            
            # Execute the extraction using orchestration engine
            result = await self.orchestration_engine.execute_extraction(
                job_id=job_id,
                property_url=job.property_url,
                execution_strategy=job.execution_strategy,
                progress_callback=self._progress_callback
            )
            
            if result['success']:
                # Update job with results
                job.extracted_data = result.get('extracted_data')
                job.merged_data = result.get('merged_data')
                job.competitor_analysis = result.get('competitor_analysis')
                job.quality_score = result.get('quality_score')
                job.current_phase = "completed"
                
                # Mark job as completed
                self.memory_store.mark_job_completed(job_id)
                
                # Add completion event
                self.memory_store.add_progress_event(
                    job_id=job_id,
                    event_type="job_completed",
                    message="Job completed successfully",
                    progress_percentage=100.0
                )
                
                logger.info(f"Worker {worker_id} completed job {job_id}")
                
            else:
                # Handle job failure
                error_message = result.get('error', 'Unknown error occurred')
                
                # Mark job as failed
                self.memory_store.mark_job_failed(job_id, error_message)
                
                # Add failure event
                self.memory_store.add_progress_event(
                    job_id=job_id,
                    event_type="job_failed",
                    message=f"Job failed: {error_message}",
                    progress_percentage=job.progress_percentage
                )
                
                logger.error(f"Worker {worker_id} failed job {job_id}: {error_message}")
            
        except Exception as e:
            logger.error(f"Error processing job {job_id} in worker {worker_id}: {str(e)}")
            
            # Mark job as failed
            self.memory_store.mark_job_failed(job_id, str(e))
            
            # Add failure event
            self.memory_store.add_progress_event(
                job_id=job_id,
                event_type="job_error",
                message=f"Job error: {str(e)}",
                progress_percentage=job.progress_percentage if 'job' in locals() else 0.0
            )
            
        finally:
            # Clean up worker assignment
            await self._release_worker(worker_id)
    
    async def _progress_callback(self, job_id: str, progress_data: dict):
        """Callback for progress updates during job execution"""
        try:
            # Update job progress (monotonic, aggregated across nodes)
            job = self.memory_store.get_job(job_id)
            if job:
                phase = progress_data.get('current_phase', job.current_phase)
                computed_progress = self._compute_overall_progress(job_id, phase)
                # Never decrease progress
                job.progress_percentage = max(job.progress_percentage, computed_progress)
                job.current_phase = phase
                self.memory_store.update_job(job)
            
            # Add progress event
            self.memory_store.add_progress_event(
                job_id=job_id,
                event_type=progress_data.get('event_type', 'progress_update'),
                message=progress_data.get('message', 'Progress update'),
                progress_percentage=job.progress_percentage,
                metadata=progress_data.get('metadata')
            )
            
        except Exception as e:
            logger.error(f"Error in progress callback for job {job_id}: {str(e)}")

    def _compute_overall_progress(self, job_id: str, phase: str) -> float:
        """Compute overall job progress from node executions and phase."""
        try:
            node_execs = self.memory_store.get_node_executions_for_job(job_id)
            total = len(node_execs)
            if total == 0:
                # Early stage before nodes are created
                return 10.0 if phase else 0.0
            completed = sum(1 for n in node_execs if n.status.value == 'completed')
            running = sum(1 for n in node_execs if n.status.value == 'running')
            failed = sum(1 for n in node_execs if n.status.value == 'failed')

            # Base 10% after job start, 80% allocated to node work, 10% to finalization
            node_component = 0.0
            if total > 0:
                node_component = (completed / total) * 80.0 + (running / total) * 20.0

            progress = 10.0 + node_component

            # Phase overrides for later stages
            if phase == 'merging_data':
                progress = max(progress, 80.0)
            elif phase == 'competitor_analysis':
                progress = max(progress, 90.0)
            elif phase == 'finalizing':
                progress = max(progress, 95.0)

            return min(100.0, round(progress, 1))
        except Exception:
            return 10.0
    
    async def _release_worker(self, worker_id: str):
        """Release a worker from its current job"""
        async with self._lock:
            if worker_id in self.workers:
                worker = self.workers[worker_id]
                if worker.current_job_id:
                    worker.jobs_processed += 1
                
                worker.current_job_id = None
                worker.last_activity = datetime.now()
                
                logger.debug(f"Released worker {worker_id}")
    
    async def get_queue_stats(self) -> QueueStats:
        """Get current queue statistics"""
        async with self._lock:
            memory_stats = self.memory_store.get_queue_stats()
            
            active_workers = len([w for w in self.workers.values() 
                                if w.is_active and w.current_job_id])
            
            return QueueStats(
                active_workers=active_workers,
                queue_length=memory_stats.queue_length,
                running_jobs=memory_stats.running_jobs,
                completed_jobs=memory_stats.completed_jobs,
                failed_jobs=memory_stats.failed_jobs,
                total_jobs=memory_stats.total_jobs
            )
    
    async def get_worker_info(self) -> List[Dict]:
        """Get information about all workers"""
        async with self._lock:
            workers_info = []
            for worker in self.workers.values():
                workers_info.append({
                    'worker_id': worker.worker_id,
                    'is_active': worker.is_active,
                    'current_job_id': worker.current_job_id,
                    'jobs_processed': worker.jobs_processed,
                    'last_activity': worker.last_activity.isoformat()
                })
            
            return workers_info

# Global job queue instance
_job_queue = None
_queue_lock = threading.Lock()

async def initialize_job_queue(max_concurrent_jobs: int = 3):
    """Initialize the global job queue"""
    global _job_queue
    with _queue_lock:
        if _job_queue is None:
            _job_queue = JobQueueMemory(max_concurrent_jobs=max_concurrent_jobs)
            await _job_queue.start()
            logger.info("Job queue worker started")

def get_job_queue() -> JobQueueMemory:
    """Get the global job queue instance"""
    global _job_queue
    with _queue_lock:
        if _job_queue is None:
            raise RuntimeError("Job queue not initialized. Call initialize_job_queue() first.")
        return _job_queue

async def shutdown_job_queue():
    """Shutdown the global job queue"""
    global _job_queue
    with _queue_lock:
        if _job_queue is not None:
            await _job_queue.stop()
            _job_queue = None
            logger.info("Job queue shutdown")

