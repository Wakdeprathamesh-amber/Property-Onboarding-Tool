import asyncio
import time
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import heapq
import threading
from concurrent.futures import ThreadPoolExecutor

from src.models.property import PropertyExtractionJob, ExtractionStatus
from src.orchestration.async_engine import get_orchestration_engine, ExecutionStrategy, OrchestrationResult
from src.utils.config import get_config
from src.utils.logging_config import get_logger

class JobPriority(Enum):
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4

@dataclass
class QueuedJob:
    """Represents a job in the queue"""
    job_id: int
    priority: JobPriority
    strategy: ExecutionStrategy
    created_at: datetime
    scheduled_at: Optional[datetime] = None
    max_retries: int = 3
    retry_count: int = 0
    callback: Optional[Callable[[OrchestrationResult], None]] = None
    
    def __lt__(self, other):
        """For priority queue ordering"""
        # Higher priority value = higher priority in queue
        # Earlier scheduled time = higher priority
        if self.priority.value != other.priority.value:
            return self.priority.value > other.priority.value
        
        scheduled_self = self.scheduled_at or self.created_at
        scheduled_other = other.scheduled_at or other.created_at
        return scheduled_self < scheduled_other

@dataclass
class QueueStats:
    """Queue statistics"""
    total_jobs: int = 0
    pending_jobs: int = 0
    running_jobs: int = 0
    completed_jobs: int = 0
    failed_jobs: int = 0
    average_execution_time: float = 0.0
    queue_length: int = 0
    active_workers: int = 0

class JobQueue:
    """Advanced job queue with priority scheduling and load balancing"""
    
    def __init__(self, max_concurrent_jobs: int = 2):
        self.config = get_config()
        self.logger = get_logger()
        self.orchestration_engine = get_orchestration_engine()
        
        # Queue configuration
        self.max_concurrent_jobs = max_concurrent_jobs
        self.max_queue_size = 100
        
        # Queue data structures
        self._queue: List[QueuedJob] = []
        self._queue_lock = asyncio.Lock()
        self._running_jobs: Dict[int, asyncio.Task] = {}
        self._completed_jobs: Dict[int, OrchestrationResult] = {}
        self._failed_jobs: Dict[int, str] = {}
        
        # Queue control
        self._is_running = False
        self._worker_task: Optional[asyncio.Task] = None
        self._stats = QueueStats()
        
        # Event callbacks
        self._job_started_callbacks: List[Callable[[int], None]] = []
        self._job_completed_callbacks: List[Callable[[OrchestrationResult], None]] = []
        self._job_failed_callbacks: List[Callable[[int, str], None]] = []
    
    async def start(self):
        """Start the job queue worker"""
        if self._is_running:
            return
        
        self._is_running = True
        self._worker_task = asyncio.create_task(self._worker_loop())
        self.logger.info("Job queue started")
    
    async def stop(self):
        """Stop the job queue worker"""
        if not self._is_running:
            return
        
        self._is_running = False
        
        # Cancel worker task
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        
        # Cancel running jobs
        for job_id, task in self._running_jobs.items():
            task.cancel()
            self.logger.info(f"Cancelled running job {job_id}")
        
        # Wait for running jobs to complete
        if self._running_jobs:
            await asyncio.gather(*self._running_jobs.values(), return_exceptions=True)
        
        self.logger.info("Job queue stopped")
    
    async def enqueue_job(self, job_id: int, priority: JobPriority = JobPriority.NORMAL,
                         strategy: ExecutionStrategy = ExecutionStrategy.PARALLEL,
                         scheduled_at: Optional[datetime] = None,
                         callback: Optional[Callable[[OrchestrationResult], None]] = None) -> bool:
        """Enqueue a job for processing"""
        async with self._queue_lock:
            # Check queue size limit
            if len(self._queue) >= self.max_queue_size:
                self.logger.warning(f"Queue is full, cannot enqueue job {job_id}")
                return False
            
            # Check if job is already queued or running
            if any(qj.job_id == job_id for qj in self._queue) or job_id in self._running_jobs:
                self.logger.warning(f"Job {job_id} is already queued or running")
                return False
            
            # Create queued job
            queued_job = QueuedJob(
                job_id=job_id,
                priority=priority,
                strategy=strategy,
                created_at=datetime.utcnow(),
                scheduled_at=scheduled_at,
                callback=callback
            )
            
            # Add to priority queue
            heapq.heappush(self._queue, queued_job)
            self._stats.queue_length = len(self._queue)
            self._stats.pending_jobs += 1
            
            self.logger.info(f"Enqueued job {job_id} with priority {priority.name}")
            return True
    
    async def dequeue_job(self, job_id: int) -> bool:
        """Remove a job from the queue"""
        async with self._queue_lock:
            # Find and remove job from queue
            for i, queued_job in enumerate(self._queue):
                if queued_job.job_id == job_id:
                    del self._queue[i]
                    heapq.heapify(self._queue)  # Restore heap property
                    self._stats.queue_length = len(self._queue)
                    self._stats.pending_jobs -= 1
                    self.logger.info(f"Dequeued job {job_id}")
                    return True
            
            return False
    
    async def get_job_status(self, job_id: int) -> Optional[str]:
        """Get the current status of a job in the queue"""
        # Check if running
        if job_id in self._running_jobs:
            return "running"
        
        # Check if completed
        if job_id in self._completed_jobs:
            return "completed"
        
        # Check if failed
        if job_id in self._failed_jobs:
            return "failed"
        
        # Check if queued
        async with self._queue_lock:
            if any(qj.job_id == job_id for qj in self._queue):
                return "queued"
        
        return None
    
    async def get_job_result(self, job_id: int) -> Optional[OrchestrationResult]:
        """Get the result of a completed job"""
        return self._completed_jobs.get(job_id)
    
    async def get_queue_stats(self) -> QueueStats:
        """Get current queue statistics"""
        async with self._queue_lock:
            self._stats.queue_length = len(self._queue)
            self._stats.active_workers = len(self._running_jobs)
            self._stats.running_jobs = len(self._running_jobs)
            
            return self._stats
    
    async def get_queued_jobs(self) -> List[Dict[str, Any]]:
        """Get list of queued jobs"""
        async with self._queue_lock:
            jobs = []
            for queued_job in sorted(self._queue):
                jobs.append({
                    'job_id': queued_job.job_id,
                    'priority': queued_job.priority.name,
                    'strategy': queued_job.strategy.value,
                    'created_at': queued_job.created_at.isoformat(),
                    'scheduled_at': queued_job.scheduled_at.isoformat() if queued_job.scheduled_at else None,
                    'retry_count': queued_job.retry_count
                })
            return jobs
    
    def add_job_started_callback(self, callback: Callable[[int], None]):
        """Add callback for when a job starts"""
        self._job_started_callbacks.append(callback)
    
    def add_job_completed_callback(self, callback: Callable[[OrchestrationResult], None]):
        """Add callback for when a job completes"""
        self._job_completed_callbacks.append(callback)
    
    def add_job_failed_callback(self, callback: Callable[[int, str], None]):
        """Add callback for when a job fails"""
        self._job_failed_callbacks.append(callback)
    
    async def _worker_loop(self):
        """Main worker loop for processing jobs"""
        self.logger.info("Job queue worker started")
        
        while self._is_running:
            try:
                # Check if we can process more jobs
                if len(self._running_jobs) >= self.max_concurrent_jobs:
                    await asyncio.sleep(1)
                    continue
                
                # Get next job from queue
                queued_job = await self._get_next_job()
                if not queued_job:
                    await asyncio.sleep(1)
                    continue
                
                # Check if job is scheduled for future
                now = datetime.utcnow()
                if queued_job.scheduled_at and queued_job.scheduled_at > now:
                    # Put job back in queue
                    async with self._queue_lock:
                        heapq.heappush(self._queue, queued_job)
                    await asyncio.sleep(1)
                    continue
                
                # Start job execution
                await self._start_job_execution(queued_job)
                
            except Exception as e:
                self.logger.error(f"Error in worker loop: {str(e)}", exc_info=True)
                await asyncio.sleep(5)  # Wait before retrying
    
    async def _get_next_job(self) -> Optional[QueuedJob]:
        """Get the next job from the priority queue"""
        async with self._queue_lock:
            if not self._queue:
                return None
            
            queued_job = heapq.heappop(self._queue)
            self._stats.queue_length = len(self._queue)
            self._stats.pending_jobs -= 1
            
            return queued_job
    
    async def _start_job_execution(self, queued_job: QueuedJob):
        """Start execution of a queued job"""
        job_id = queued_job.job_id
        
        try:
            # Create execution task
            task = asyncio.create_task(
                self._execute_job_with_monitoring(queued_job)
            )
            
            # Track running job
            self._running_jobs[job_id] = task
            self._stats.running_jobs += 1
            
            # Notify callbacks
            for callback in self._job_started_callbacks:
                try:
                    callback(job_id)
                except Exception as e:
                    self.logger.error(f"Error in job started callback: {str(e)}")
            
            self.logger.info(f"Started execution of job {job_id}")
            
        except Exception as e:
            self.logger.error(f"Failed to start job {job_id}: {str(e)}", exc_info=True)
            await self._handle_job_failure(queued_job, str(e))
    
    async def _execute_job_with_monitoring(self, queued_job: QueuedJob):
        """Execute job with monitoring and error handling"""
        job_id = queued_job.job_id
        start_time = time.time()
        
        try:
            # Execute job using orchestration engine
            result = await self.orchestration_engine.orchestrate_extraction(
                job_id, queued_job.strategy
            )
            
            execution_time = time.time() - start_time
            
            # Update statistics
            self._update_execution_stats(execution_time)
            
            if result.success:
                await self._handle_job_completion(queued_job, result)
            else:
                await self._handle_job_failure(queued_job, result.error_message or "Unknown error")
            
        except Exception as e:
            execution_time = time.time() - start_time
            self._update_execution_stats(execution_time)
            
            error_message = str(e)
            self.logger.error(f"Job {job_id} execution failed: {error_message}", exc_info=True)
            await self._handle_job_failure(queued_job, error_message)
        
        finally:
            # Remove from running jobs
            if job_id in self._running_jobs:
                del self._running_jobs[job_id]
                self._stats.running_jobs -= 1
    
    async def _handle_job_completion(self, queued_job: QueuedJob, result: OrchestrationResult):
        """Handle successful job completion"""
        job_id = queued_job.job_id
        
        # Store result
        self._completed_jobs[job_id] = result
        self._stats.completed_jobs += 1
        
        # Call job-specific callback
        if queued_job.callback:
            try:
                queued_job.callback(result)
            except Exception as e:
                self.logger.error(f"Error in job callback for {job_id}: {str(e)}")
        
        # Call global callbacks
        for callback in self._job_completed_callbacks:
            try:
                callback(result)
            except Exception as e:
                self.logger.error(f"Error in job completed callback: {str(e)}")
        
        self.logger.info(f"Job {job_id} completed successfully")
    
    async def _handle_job_failure(self, queued_job: QueuedJob, error_message: str):
        """Handle job failure with retry logic"""
        job_id = queued_job.job_id
        
        # Check if we should retry
        if queued_job.retry_count < queued_job.max_retries:
            queued_job.retry_count += 1
            
            # Calculate retry delay (exponential backoff)
            retry_delay = min(300, 30 * (2 ** (queued_job.retry_count - 1)))  # Max 5 minutes
            queued_job.scheduled_at = datetime.utcnow() + timedelta(seconds=retry_delay)
            
            # Re-queue the job
            async with self._queue_lock:
                heapq.heappush(self._queue, queued_job)
                self._stats.queue_length = len(self._queue)
                self._stats.pending_jobs += 1
            
            self.logger.info(f"Job {job_id} failed, scheduled for retry #{queued_job.retry_count} in {retry_delay} seconds")
            
        else:
            # Max retries exceeded, mark as failed
            self._failed_jobs[job_id] = error_message
            self._stats.failed_jobs += 1
            
            # Call failure callbacks
            for callback in self._job_failed_callbacks:
                try:
                    callback(job_id, error_message)
                except Exception as e:
                    self.logger.error(f"Error in job failed callback: {str(e)}")
            
            self.logger.error(f"Job {job_id} failed permanently after {queued_job.retry_count} retries: {error_message}")
    
    def _update_execution_stats(self, execution_time: float):
        """Update execution statistics"""
        total_executions = self._stats.completed_jobs + self._stats.failed_jobs + 1
        
        if self._stats.average_execution_time == 0:
            self._stats.average_execution_time = execution_time
        else:
            # Running average
            self._stats.average_execution_time = (
                (self._stats.average_execution_time * (total_executions - 1) + execution_time) / 
                total_executions
            )
    
    async def cleanup_old_results(self, max_age_hours: int = 24):
        """Clean up old completed and failed job results"""
        cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)
        
        # Clean completed jobs (we don't have timestamps, so clean based on count)
        if len(self._completed_jobs) > 100:  # Keep last 100 results
            oldest_jobs = sorted(self._completed_jobs.keys())[:len(self._completed_jobs) - 100]
            for job_id in oldest_jobs:
                del self._completed_jobs[job_id]
        
        # Clean failed jobs
        if len(self._failed_jobs) > 50:  # Keep last 50 failed jobs
            oldest_jobs = sorted(self._failed_jobs.keys())[:len(self._failed_jobs) - 50]
            for job_id in oldest_jobs:
                del self._failed_jobs[job_id]
        
        self.logger.info("Cleaned up old job results")

# Global job queue instance
_job_queue = None

def get_job_queue() -> JobQueue:
    """Get the global job queue instance"""
    global _job_queue
    if _job_queue is None:
        config = get_config()
        _job_queue = JobQueue(max_concurrent_jobs=2)  # Default to 2 concurrent jobs
    return _job_queue

async def initialize_job_queue():
    """Initialize and start the job queue"""
    queue = get_job_queue()
    await queue.start()
    return queue

async def shutdown_job_queue():
    """Shutdown the job queue"""
    global _job_queue
    if _job_queue:
        await _job_queue.stop()
        _job_queue = None

