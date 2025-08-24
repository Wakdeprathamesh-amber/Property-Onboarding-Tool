import time
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import threading
import asyncio

from src.models.property import PropertyExtractionJob, NodeExecution, ExtractionStatus, NodeStatus
from src.utils.logging_config import get_logger

class ProgressEventType(Enum):
    JOB_STARTED = "job_started"
    JOB_COMPLETED = "job_completed"
    JOB_FAILED = "job_failed"
    NODE_STARTED = "node_started"
    NODE_COMPLETED = "node_completed"
    NODE_FAILED = "node_failed"
    NODE_RETRY = "node_retry"
    DATA_MERGE_STARTED = "data_merge_started"
    DATA_MERGE_COMPLETED = "data_merge_completed"
    COMPETITOR_ANALYSIS_STARTED = "competitor_analysis_started"
    COMPETITOR_ANALYSIS_COMPLETED = "competitor_analysis_completed"

@dataclass
class ProgressEvent:
    """Represents a progress event"""
    event_type: ProgressEventType
    job_id: int
    timestamp: datetime
    node_name: Optional[str] = None
    message: str = ""
    data: Dict[str, Any] = field(default_factory=dict)

@dataclass
class NodeProgress:
    """Progress information for a single node"""
    node_name: str
    status: NodeStatus
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    execution_time: Optional[float] = None
    confidence_score: Optional[float] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    progress_percentage: float = 0.0

@dataclass
class JobProgress:
    """Comprehensive progress information for a job"""
    job_id: int
    status: ExtractionStatus
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    total_execution_time: Optional[float] = None
    accuracy_score: Optional[float] = None
    error_message: Optional[str] = None
    
    # Node progress
    nodes: Dict[str, NodeProgress] = field(default_factory=dict)
    
    # Overall progress
    overall_progress: float = 0.0
    estimated_completion_time: Optional[datetime] = None
    
    # Phase tracking
    current_phase: str = "initializing"
    phases_completed: List[str] = field(default_factory=list)
    
    # Statistics
    nodes_completed: int = 0
    nodes_failed: int = 0
    nodes_total: int = 4
    
    # Events
    events: List[ProgressEvent] = field(default_factory=list)

class ProgressTracker:
    """Advanced progress tracking system for extraction jobs"""
    
    def __init__(self):
        self.logger = get_logger()
        
        # Progress storage
        self._job_progress: Dict[int, JobProgress] = {}
        self._progress_lock = threading.RLock()
        
        # Event subscribers
        self._event_subscribers: List[Callable[[ProgressEvent], None]] = []
        
        # Progress calculation weights
        self._node_weights = {
            'node1_basic_info': 0.3,  # Most important
            'node2_description': 0.2,
            'node3_configuration': 0.25,
            'node4_tenancy': 0.25
        }
        
        # Phase definitions
        self._phases = [
            "initializing",
            "extracting_data",
            "merging_data", 
            "competitor_analysis",
            "finalizing"
        ]
    
    def start_job_tracking(self, job_id: int) -> JobProgress:
        """Start tracking progress for a job"""
        with self._progress_lock:
            progress = JobProgress(
                job_id=job_id,
                status=ExtractionStatus.PENDING,
                current_phase="initializing"
            )
            
            # Initialize node progress
            for node_name in self._node_weights.keys():
                progress.nodes[node_name] = NodeProgress(
                    node_name=node_name,
                    status=NodeStatus.PENDING
                )
            
            self._job_progress[job_id] = progress
            
            # Emit event
            self._emit_event(ProgressEvent(
                event_type=ProgressEventType.JOB_STARTED,
                job_id=job_id,
                timestamp=datetime.utcnow(),
                message="Job tracking started"
            ))
            
            return progress
    
    def update_job_status(self, job_id: int, status: ExtractionStatus, 
                         error_message: Optional[str] = None):
        """Update job status"""
        with self._progress_lock:
            if job_id not in self._job_progress:
                return
            
            progress = self._job_progress[job_id]
            old_status = progress.status
            progress.status = status
            
            if status == ExtractionStatus.IN_PROGRESS:
                progress.started_at = datetime.utcnow()
                progress.current_phase = "extracting_data"
            elif status in [ExtractionStatus.COMPLETED, ExtractionStatus.FAILED]:
                progress.completed_at = datetime.utcnow()
                if progress.started_at:
                    progress.total_execution_time = (
                        progress.completed_at - progress.started_at
                    ).total_seconds()
                
                if status == ExtractionStatus.COMPLETED:
                    progress.current_phase = "completed"
                    progress.overall_progress = 100.0
                    progress.phases_completed = self._phases[:-1] + ["completed"]
                else:
                    progress.current_phase = "failed"
                    progress.error_message = error_message
            
            # Update progress calculation
            self._calculate_overall_progress(job_id)
            
            # Emit event
            if status == ExtractionStatus.COMPLETED:
                self._emit_event(ProgressEvent(
                    event_type=ProgressEventType.JOB_COMPLETED,
                    job_id=job_id,
                    timestamp=datetime.utcnow(),
                    message="Job completed successfully",
                    data={"execution_time": progress.total_execution_time}
                ))
            elif status == ExtractionStatus.FAILED:
                self._emit_event(ProgressEvent(
                    event_type=ProgressEventType.JOB_FAILED,
                    job_id=job_id,
                    timestamp=datetime.utcnow(),
                    message=f"Job failed: {error_message}",
                    data={"error": error_message}
                ))
    
    def update_node_status(self, job_id: int, node_name: str, status: NodeStatus,
                          execution_time: Optional[float] = None,
                          confidence_score: Optional[float] = None,
                          error_message: Optional[str] = None,
                          retry_count: int = 0):
        """Update node status and progress"""
        with self._progress_lock:
            if job_id not in self._job_progress:
                return
            
            progress = self._job_progress[job_id]
            if node_name not in progress.nodes:
                return
            
            node_progress = progress.nodes[node_name]
            old_status = node_progress.status
            node_progress.status = status
            node_progress.retry_count = retry_count
            
            if status == NodeStatus.RUNNING:
                node_progress.started_at = datetime.utcnow()
                node_progress.progress_percentage = 10.0  # Started
                
                self._emit_event(ProgressEvent(
                    event_type=ProgressEventType.NODE_STARTED,
                    job_id=job_id,
                    timestamp=datetime.utcnow(),
                    node_name=node_name,
                    message=f"Node {node_name} started"
                ))
                
            elif status == NodeStatus.COMPLETED:
                node_progress.completed_at = datetime.utcnow()
                node_progress.execution_time = execution_time
                node_progress.confidence_score = confidence_score
                node_progress.progress_percentage = 100.0
                
                # Update job statistics
                progress.nodes_completed += 1
                
                self._emit_event(ProgressEvent(
                    event_type=ProgressEventType.NODE_COMPLETED,
                    job_id=job_id,
                    timestamp=datetime.utcnow(),
                    node_name=node_name,
                    message=f"Node {node_name} completed",
                    data={
                        "execution_time": execution_time,
                        "confidence_score": confidence_score
                    }
                ))
                
            elif status == NodeStatus.FAILED:
                node_progress.completed_at = datetime.utcnow()
                node_progress.execution_time = execution_time
                node_progress.error_message = error_message
                node_progress.progress_percentage = 0.0
                
                # Update job statistics
                progress.nodes_failed += 1
                
                if retry_count > 0:
                    self._emit_event(ProgressEvent(
                        event_type=ProgressEventType.NODE_RETRY,
                        job_id=job_id,
                        timestamp=datetime.utcnow(),
                        node_name=node_name,
                        message=f"Node {node_name} retry #{retry_count}",
                        data={"retry_count": retry_count, "error": error_message}
                    ))
                else:
                    self._emit_event(ProgressEvent(
                        event_type=ProgressEventType.NODE_FAILED,
                        job_id=job_id,
                        timestamp=datetime.utcnow(),
                        node_name=node_name,
                        message=f"Node {node_name} failed: {error_message}",
                        data={"error": error_message}
                    ))
            
            # Update overall progress
            self._calculate_overall_progress(job_id)
    
    def update_phase(self, job_id: int, phase: str, message: str = ""):
        """Update current processing phase"""
        with self._progress_lock:
            if job_id not in self._job_progress:
                return
            
            progress = self._job_progress[job_id]
            old_phase = progress.current_phase
            progress.current_phase = phase
            
            # Add to completed phases if moving forward
            if old_phase in self._phases and old_phase not in progress.phases_completed:
                progress.phases_completed.append(old_phase)
            
            # Emit phase-specific events
            if phase == "merging_data":
                self._emit_event(ProgressEvent(
                    event_type=ProgressEventType.DATA_MERGE_STARTED,
                    job_id=job_id,
                    timestamp=datetime.utcnow(),
                    message="Starting data merge process"
                ))
            elif phase == "competitor_analysis":
                self._emit_event(ProgressEvent(
                    event_type=ProgressEventType.COMPETITOR_ANALYSIS_STARTED,
                    job_id=job_id,
                    timestamp=datetime.utcnow(),
                    message="Starting competitor analysis"
                ))
    
    def mark_data_merge_completed(self, job_id: int, success: bool, quality_score: float = 0.0):
        """Mark data merge phase as completed"""
        with self._progress_lock:
            if job_id not in self._job_progress:
                return
            
            progress = self._job_progress[job_id]
            progress.accuracy_score = quality_score
            
            if "merging_data" not in progress.phases_completed:
                progress.phases_completed.append("merging_data")
            
            self._emit_event(ProgressEvent(
                event_type=ProgressEventType.DATA_MERGE_COMPLETED,
                job_id=job_id,
                timestamp=datetime.utcnow(),
                message=f"Data merge {'completed' if success else 'failed'}",
                data={"success": success, "quality_score": quality_score}
            ))
    
    def mark_competitor_analysis_completed(self, job_id: int, competitors_found: int):
        """Mark competitor analysis as completed"""
        with self._progress_lock:
            if job_id not in self._job_progress:
                return
            
            progress = self._job_progress[job_id]
            
            if "competitor_analysis" not in progress.phases_completed:
                progress.phases_completed.append("competitor_analysis")
            
            self._emit_event(ProgressEvent(
                event_type=ProgressEventType.COMPETITOR_ANALYSIS_COMPLETED,
                job_id=job_id,
                timestamp=datetime.utcnow(),
                message=f"Competitor analysis completed, found {competitors_found} competitors",
                data={"competitors_found": competitors_found}
            ))
    
    def get_job_progress(self, job_id: int) -> Optional[JobProgress]:
        """Get current progress for a job"""
        with self._progress_lock:
            return self._job_progress.get(job_id)
    
    def get_all_active_jobs(self) -> List[JobProgress]:
        """Get progress for all active jobs"""
        with self._progress_lock:
            active_jobs = []
            for progress in self._job_progress.values():
                if progress.status in [ExtractionStatus.PENDING, ExtractionStatus.IN_PROGRESS]:
                    active_jobs.append(progress)
            return active_jobs
    
    def get_job_events(self, job_id: int, limit: int = 50) -> List[ProgressEvent]:
        """Get recent events for a job"""
        with self._progress_lock:
            if job_id not in self._job_progress:
                return []
            
            events = self._job_progress[job_id].events
            return events[-limit:] if len(events) > limit else events
    
    def subscribe_to_events(self, callback: Callable[[ProgressEvent], None]):
        """Subscribe to progress events"""
        self._event_subscribers.append(callback)
    
    def unsubscribe_from_events(self, callback: Callable[[ProgressEvent], None]):
        """Unsubscribe from progress events"""
        if callback in self._event_subscribers:
            self._event_subscribers.remove(callback)
    
    def cleanup_completed_jobs(self, max_age_hours: int = 24):
        """Clean up old completed job progress data"""
        cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)
        
        with self._progress_lock:
            jobs_to_remove = []
            
            for job_id, progress in self._job_progress.items():
                if (progress.status in [ExtractionStatus.COMPLETED, ExtractionStatus.FAILED] and
                    progress.completed_at and progress.completed_at < cutoff_time):
                    jobs_to_remove.append(job_id)
            
            for job_id in jobs_to_remove:
                del self._job_progress[job_id]
            
            if jobs_to_remove:
                self.logger.info(f"Cleaned up progress data for {len(jobs_to_remove)} old jobs")
    
    def _calculate_overall_progress(self, job_id: int):
        """Calculate overall progress percentage for a job"""
        with self._progress_lock:
            if job_id not in self._job_progress:
                return
            
            progress = self._job_progress[job_id]
            
            # Calculate weighted progress based on node completion
            total_weight = 0.0
            weighted_progress = 0.0
            
            for node_name, node_progress in progress.nodes.items():
                weight = self._node_weights.get(node_name, 0.25)
                total_weight += weight
                
                if node_progress.status == NodeStatus.COMPLETED:
                    weighted_progress += weight * 100.0
                elif node_progress.status == NodeStatus.RUNNING:
                    weighted_progress += weight * node_progress.progress_percentage
                elif node_progress.status == NodeStatus.FAILED:
                    # Failed nodes contribute 0 to progress
                    pass
            
            # Base progress from node execution
            base_progress = weighted_progress / total_weight if total_weight > 0 else 0.0
            
            # Add bonus progress for completed phases
            phase_bonus = len(progress.phases_completed) * 2.0  # 2% per completed phase
            
            # Calculate final progress
            progress.overall_progress = min(100.0, base_progress + phase_bonus)
            
            # Estimate completion time if job is in progress
            if (progress.status == ExtractionStatus.IN_PROGRESS and 
                progress.started_at and progress.overall_progress > 10):
                
                elapsed_time = (datetime.utcnow() - progress.started_at).total_seconds()
                estimated_total_time = elapsed_time / (progress.overall_progress / 100.0)
                remaining_time = estimated_total_time - elapsed_time
                
                if remaining_time > 0:
                    progress.estimated_completion_time = datetime.utcnow() + timedelta(seconds=remaining_time)
    
    def _emit_event(self, event: ProgressEvent):
        """Emit a progress event to subscribers"""
        # Add event to job's event history
        if event.job_id in self._job_progress:
            self._job_progress[event.job_id].events.append(event)
            
            # Keep only last 100 events per job
            events = self._job_progress[event.job_id].events
            if len(events) > 100:
                self._job_progress[event.job_id].events = events[-100:]
        
        # Notify subscribers
        for subscriber in self._event_subscribers:
            try:
                subscriber(event)
            except Exception as e:
                self.logger.error(f"Error in progress event subscriber: {str(e)}")
    
    def get_progress_summary(self, job_id: int) -> Dict[str, Any]:
        """Get a summary of job progress for API responses"""
        with self._progress_lock:
            if job_id not in self._job_progress:
                return {}
            
            progress = self._job_progress[job_id]
            
            return {
                "job_id": job_id,
                "status": progress.status.value,
                "overall_progress": round(progress.overall_progress, 1),
                "current_phase": progress.current_phase,
                "phases_completed": progress.phases_completed,
                "nodes_completed": progress.nodes_completed,
                "nodes_failed": progress.nodes_failed,
                "nodes_total": progress.nodes_total,
                "started_at": progress.started_at.isoformat() if progress.started_at else None,
                "estimated_completion": progress.estimated_completion_time.isoformat() if progress.estimated_completion_time else None,
                "execution_time": progress.total_execution_time,
                "accuracy_score": progress.accuracy_score,
                "error_message": progress.error_message,
                "node_details": {
                    name: {
                        "status": node.status.value,
                        "progress": round(node.progress_percentage, 1),
                        "execution_time": node.execution_time,
                        "confidence_score": node.confidence_score,
                        "retry_count": node.retry_count,
                        "error": node.error_message
                    }
                    for name, node in progress.nodes.items()
                }
            }

# Global progress tracker instance
_progress_tracker = None

def get_progress_tracker() -> ProgressTracker:
    """Get the global progress tracker instance"""
    global _progress_tracker
    if _progress_tracker is None:
        _progress_tracker = ProgressTracker()
    return _progress_tracker

