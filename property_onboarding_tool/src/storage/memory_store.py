"""
In-memory storage manager for property extraction jobs and data.
Replaces database functionality with in-memory data structures.
"""

import uuid
import time
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import threading
import json

class JobStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class JobPriority(Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"

class ExecutionStrategy(Enum):
    PARALLEL = "parallel"
    SEQUENTIAL = "sequential"
    HYBRID = "hybrid"

class NodeStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass
class NodeExecution:
    """Represents the execution of a single extraction node"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    job_id: str = ""
    node_name: str = ""
    node_type: str = ""
    status: NodeStatus = NodeStatus.PENDING
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    execution_time: Optional[float] = None
    extracted_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    confidence_score: Optional[float] = None
    # Optional key to associate node execution with a specific configuration
    config_key: Optional[str] = None
    # Data quality indicators per node (e.g., completeness, warning/error counts)
    quality_metrics: Optional[Dict[str, Any]] = None
    # Categorized error type for easier debugging/aggregation
    error_category: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

@dataclass
class PropertyExtractionJob:
    """Represents a property extraction job"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    property_url: str = ""
    status: JobStatus = JobStatus.PENDING
    priority: JobPriority = JobPriority.NORMAL
    execution_strategy: ExecutionStrategy = ExecutionStrategy.PARALLEL
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    execution_time: Optional[float] = None
    extracted_data: Optional[Dict[str, Any]] = None
    merged_data: Optional[Dict[str, Any]] = None
    competitor_analysis: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    progress_percentage: float = 0.0
    current_phase: str = "initializing"
    quality_score: Optional[float] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    # Node executions
    node_executions: List[NodeExecution] = field(default_factory=list)

@dataclass
class ProgressEvent:
    """Represents a progress event for a job"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    job_id: str = ""
    event_type: str = ""
    message: str = ""
    progress_percentage: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Optional[Dict[str, Any]] = None

@dataclass
class QueueStats:
    """Queue statistics"""
    active_workers: int = 0
    queue_length: int = 0
    running_jobs: int = 0
    completed_jobs: int = 0
    failed_jobs: int = 0
    total_jobs: int = 0

class MemoryStore:
    """In-memory storage manager for all application data"""
    
    def __init__(self):
        self._jobs: Dict[str, PropertyExtractionJob] = {}
        self._node_executions: Dict[str, NodeExecution] = {}
        self._progress_events: Dict[str, List[ProgressEvent]] = {}
        self._queue: List[str] = []  # Job IDs in queue order
        self._running_jobs: Dict[str, str] = {}  # job_id -> worker_id
        self._lock = threading.RLock()
        
    # Job Management
    def create_job(self, property_url: str, priority: JobPriority = JobPriority.NORMAL, 
                   execution_strategy: ExecutionStrategy = ExecutionStrategy.PARALLEL) -> PropertyExtractionJob:
        """Create a new extraction job"""
        with self._lock:
            job = PropertyExtractionJob(
                property_url=property_url,
                priority=priority,
                execution_strategy=execution_strategy
            )
            self._jobs[job.id] = job
            self._progress_events[job.id] = []
            return job
    
    def get_job(self, job_id: str) -> Optional[PropertyExtractionJob]:
        """Get a job by ID"""
        with self._lock:
            return self._jobs.get(job_id)
    
    def update_job(self, job: PropertyExtractionJob) -> None:
        """Update a job"""
        with self._lock:
            job.updated_at = datetime.now()
            self._jobs[job.id] = job
    
    def get_all_jobs(self, status: Optional[JobStatus] = None, 
                     priority: Optional[JobPriority] = None) -> List[PropertyExtractionJob]:
        """Get all jobs with optional filtering"""
        with self._lock:
            jobs = list(self._jobs.values())
            if status:
                jobs = [job for job in jobs if job.status == status]
            if priority:
                jobs = [job for job in jobs if job.priority == priority]
            return sorted(jobs, key=lambda x: x.created_at, reverse=True)
    
    def delete_job(self, job_id: str) -> bool:
        """Delete a job and its related data"""
        with self._lock:
            if job_id in self._jobs:
                # Remove from queue if present
                if job_id in self._queue:
                    self._queue.remove(job_id)
                
                # Remove from running jobs
                if job_id in self._running_jobs:
                    del self._running_jobs[job_id]
                
                # Remove job and related data
                del self._jobs[job_id]
                
                # Remove node executions
                to_remove = [ne_id for ne_id, ne in self._node_executions.items() 
                           if ne.job_id == job_id]
                for ne_id in to_remove:
                    del self._node_executions[ne_id]
                
                # Remove progress events
                if job_id in self._progress_events:
                    del self._progress_events[job_id]
                
                return True
            return False
    
    # Node Execution Management
    def create_node_execution(self, job_id: str, node_name: str, 
                            node_type: str, config_key: Optional[str] = None) -> NodeExecution:
        """Create a new node execution"""
        with self._lock:
            node_exec = NodeExecution(
                job_id=job_id,
                node_name=node_name,
                node_type=node_type,
                config_key=config_key
            )
            self._node_executions[node_exec.id] = node_exec
            
            # Add to job's node executions
            if job_id in self._jobs:
                self._jobs[job_id].node_executions.append(node_exec)
            
            return node_exec
    
    def update_node_execution(self, node_exec: NodeExecution) -> None:
        """Update a node execution"""
        with self._lock:
            node_exec.updated_at = datetime.now()
            self._node_executions[node_exec.id] = node_exec
    
    def get_node_executions_for_job(self, job_id: str) -> List[NodeExecution]:
        """Get all node executions for a job"""
        with self._lock:
            return [ne for ne in self._node_executions.values() if ne.job_id == job_id]
    
    # Progress Event Management
    def add_progress_event(self, job_id: str, event_type: str, message: str, 
                          progress_percentage: float = 0.0, 
                          metadata: Optional[Dict[str, Any]] = None) -> ProgressEvent:
        """Add a progress event for a job"""
        with self._lock:
            event = ProgressEvent(
                job_id=job_id,
                event_type=event_type,
                message=message,
                progress_percentage=progress_percentage,
                metadata=metadata
            )
            
            if job_id not in self._progress_events:
                self._progress_events[job_id] = []
            
            self._progress_events[job_id].append(event)
            
            # Update job progress
            if job_id in self._jobs:
                self._jobs[job_id].progress_percentage = progress_percentage
                self._jobs[job_id].updated_at = datetime.now()
            
            return event
    
    def get_progress_events(self, job_id: str) -> List[ProgressEvent]:
        """Get all progress events for a job"""
        with self._lock:
            return self._progress_events.get(job_id, [])
    
    # Queue Management
    def enqueue_job(self, job_id: str) -> None:
        """Add a job to the processing queue"""
        with self._lock:
            if job_id not in self._queue and job_id in self._jobs:
                # Insert based on priority
                job = self._jobs[job_id]
                priority_order = {
                    JobPriority.URGENT: 0,
                    JobPriority.HIGH: 1,
                    JobPriority.NORMAL: 2,
                    JobPriority.LOW: 3
                }
                
                job_priority = priority_order.get(job.priority, 2)
                
                # Find insertion point
                insert_index = len(self._queue)
                for i, queued_job_id in enumerate(self._queue):
                    queued_job = self._jobs.get(queued_job_id)
                    if queued_job:
                        queued_priority = priority_order.get(queued_job.priority, 2)
                        if job_priority < queued_priority:
                            insert_index = i
                            break
                
                self._queue.insert(insert_index, job_id)
                
                # Update job status
                job.status = JobStatus.PENDING
                self.update_job(job)
    
    def dequeue_job(self) -> Optional[str]:
        """Get the next job from the queue"""
        with self._lock:
            if self._queue:
                return self._queue.pop(0)
            return None
    
    def mark_job_running(self, job_id: str, worker_id: str) -> None:
        """Mark a job as running"""
        with self._lock:
            self._running_jobs[job_id] = worker_id
            if job_id in self._jobs:
                self._jobs[job_id].status = JobStatus.RUNNING
                self._jobs[job_id].start_time = datetime.now()
                self.update_job(self._jobs[job_id])
    
    def mark_job_completed(self, job_id: str) -> None:
        """Mark a job as completed"""
        with self._lock:
            if job_id in self._running_jobs:
                del self._running_jobs[job_id]
            
            if job_id in self._jobs:
                job = self._jobs[job_id]
                job.status = JobStatus.COMPLETED
                job.end_time = datetime.now()
                if job.start_time:
                    job.execution_time = (job.end_time - job.start_time).total_seconds()
                job.progress_percentage = 100.0
                self.update_job(job)
    
    def mark_job_failed(self, job_id: str, error_message: str) -> None:
        """Mark a job as failed"""
        with self._lock:
            if job_id in self._running_jobs:
                del self._running_jobs[job_id]
            
            if job_id in self._jobs:
                job = self._jobs[job_id]
                job.status = JobStatus.FAILED
                job.end_time = datetime.now()
                job.error_message = error_message
                if job.start_time:
                    job.execution_time = (job.end_time - job.start_time).total_seconds()
                self.update_job(job)
    
    def get_queue_stats(self) -> QueueStats:
        """Get queue statistics"""
        with self._lock:
            all_jobs = list(self._jobs.values())
            return QueueStats(
                active_workers=len(self._running_jobs),
                queue_length=len(self._queue),
                running_jobs=len([j for j in all_jobs if j.status == JobStatus.RUNNING]),
                completed_jobs=len([j for j in all_jobs if j.status == JobStatus.COMPLETED]),
                failed_jobs=len([j for j in all_jobs if j.status == JobStatus.FAILED]),
                total_jobs=len(all_jobs)
            )
    
    # Data Export/Import (for persistence if needed)
    def export_data(self) -> Dict[str, Any]:
        """Export all data to a dictionary"""
        with self._lock:
            return {
                'jobs': {job_id: self._job_to_dict(job) for job_id, job in self._jobs.items()},
                'node_executions': {ne_id: self._node_exec_to_dict(ne) for ne_id, ne in self._node_executions.items()},
                'progress_events': {job_id: [self._event_to_dict(event) for event in events] 
                                  for job_id, events in self._progress_events.items()},
                'queue': self._queue.copy(),
                'running_jobs': self._running_jobs.copy()
            }
    
    def import_data(self, data: Dict[str, Any]) -> None:
        """Import data from a dictionary"""
        with self._lock:
            # Clear existing data
            self._jobs.clear()
            self._node_executions.clear()
            self._progress_events.clear()
            self._queue.clear()
            self._running_jobs.clear()
            
            # Import jobs
            for job_id, job_data in data.get('jobs', {}).items():
                self._jobs[job_id] = self._dict_to_job(job_data)
            
            # Import node executions
            for ne_id, ne_data in data.get('node_executions', {}).items():
                self._node_executions[ne_id] = self._dict_to_node_exec(ne_data)
            
            # Import progress events
            for job_id, events_data in data.get('progress_events', {}).items():
                self._progress_events[job_id] = [self._dict_to_event(event_data) 
                                               for event_data in events_data]
            
            # Import queue and running jobs
            self._queue = data.get('queue', [])
            self._running_jobs = data.get('running_jobs', {})
    
    # Helper methods for serialization
    def _job_to_dict(self, job: PropertyExtractionJob) -> Dict[str, Any]:
        """Convert job to dictionary"""
        return {
            'id': job.id,
            'property_url': job.property_url,
            'status': job.status.value,
            'priority': job.priority.value,
            'execution_strategy': job.execution_strategy.value,
            'start_time': job.start_time.isoformat() if job.start_time else None,
            'end_time': job.end_time.isoformat() if job.end_time else None,
            'execution_time': job.execution_time,
            'extracted_data': job.extracted_data,
            'merged_data': job.merged_data,
            'competitor_analysis': job.competitor_analysis,
            'error_message': job.error_message,
            'retry_count': job.retry_count,
            'max_retries': job.max_retries,
            'progress_percentage': job.progress_percentage,
            'current_phase': job.current_phase,
            'quality_score': job.quality_score,
            'created_at': job.created_at.isoformat(),
            'updated_at': job.updated_at.isoformat()
        }
    
    def _dict_to_job(self, data: Dict[str, Any]) -> PropertyExtractionJob:
        """Convert dictionary to job"""
        job = PropertyExtractionJob(
            id=data['id'],
            property_url=data['property_url'],
            status=JobStatus(data['status']),
            priority=JobPriority(data['priority']),
            execution_strategy=ExecutionStrategy(data['execution_strategy']),
            start_time=datetime.fromisoformat(data['start_time']) if data['start_time'] else None,
            end_time=datetime.fromisoformat(data['end_time']) if data['end_time'] else None,
            execution_time=data['execution_time'],
            extracted_data=data['extracted_data'],
            merged_data=data['merged_data'],
            competitor_analysis=data['competitor_analysis'],
            error_message=data['error_message'],
            retry_count=data['retry_count'],
            max_retries=data['max_retries'],
            progress_percentage=data['progress_percentage'],
            current_phase=data['current_phase'],
            quality_score=data['quality_score'],
            created_at=datetime.fromisoformat(data['created_at']),
            updated_at=datetime.fromisoformat(data['updated_at'])
        )
        return job
    
    def _node_exec_to_dict(self, node_exec: NodeExecution) -> Dict[str, Any]:
        """Convert node execution to dictionary"""
        return {
            'id': node_exec.id,
            'job_id': node_exec.job_id,
            'node_name': node_exec.node_name,
            'node_type': node_exec.node_type,
            'status': node_exec.status.value,
            'start_time': node_exec.start_time.isoformat() if node_exec.start_time else None,
            'end_time': node_exec.end_time.isoformat() if node_exec.end_time else None,
            'execution_time': node_exec.execution_time,
            'extracted_data': node_exec.extracted_data,
            'error_message': node_exec.error_message,
            'retry_count': node_exec.retry_count,
            'confidence_score': node_exec.confidence_score,
            'config_key': node_exec.config_key,
            'quality_metrics': node_exec.quality_metrics,
            'error_category': node_exec.error_category,
            'created_at': node_exec.created_at.isoformat(),
            'updated_at': node_exec.updated_at.isoformat()
        }
    
    def _dict_to_node_exec(self, data: Dict[str, Any]) -> NodeExecution:
        """Convert dictionary to node execution"""
        return NodeExecution(
            id=data['id'],
            job_id=data['job_id'],
            node_name=data['node_name'],
            node_type=data['node_type'],
            status=NodeStatus(data['status']),
            start_time=datetime.fromisoformat(data['start_time']) if data['start_time'] else None,
            end_time=datetime.fromisoformat(data['end_time']) if data['end_time'] else None,
            execution_time=data['execution_time'],
            extracted_data=data['extracted_data'],
            error_message=data['error_message'],
            retry_count=data['retry_count'],
            confidence_score=data['confidence_score'],
            config_key=data.get('config_key'),
            quality_metrics=data.get('quality_metrics'),
            error_category=data.get('error_category'),
            created_at=datetime.fromisoformat(data['created_at']),
            updated_at=datetime.fromisoformat(data['updated_at'])
        )
    
    def _event_to_dict(self, event: ProgressEvent) -> Dict[str, Any]:
        """Convert progress event to dictionary"""
        return {
            'id': event.id,
            'job_id': event.job_id,
            'event_type': event.event_type,
            'message': event.message,
            'progress_percentage': event.progress_percentage,
            'timestamp': event.timestamp.isoformat(),
            'metadata': event.metadata
        }
    
    def _dict_to_event(self, data: Dict[str, Any]) -> ProgressEvent:
        """Convert dictionary to progress event"""
        return ProgressEvent(
            id=data['id'],
            job_id=data['job_id'],
            event_type=data['event_type'],
            message=data['message'],
            progress_percentage=data['progress_percentage'],
            timestamp=datetime.fromisoformat(data['timestamp']),
            metadata=data['metadata']
        )

# Global memory store instance
_memory_store = None
_store_lock = threading.Lock()

def get_memory_store() -> MemoryStore:
    """Get the global memory store instance"""
    global _memory_store
    with _store_lock:
        if _memory_store is None:
            _memory_store = MemoryStore()
        return _memory_store

def reset_memory_store() -> None:
    """Reset the global memory store (useful for testing)"""
    global _memory_store
    with _store_lock:
        _memory_store = MemoryStore()

