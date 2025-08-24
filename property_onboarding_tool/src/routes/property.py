from flask import Blueprint, jsonify, request
from flask_cors import cross_origin
from src.models.property import (
    PropertyExtractionJob, NodeExecution, CompetitorAnalysis, 
    ExtractionStatus, NodeStatus, db
)
from src.orchestration.job_queue import get_job_queue, JobPriority
from src.orchestration.async_engine import ExecutionStrategy
from src.orchestration.progress_tracker import get_progress_tracker
from datetime import datetime
import validators
import asyncio
import threading
from typing import Dict, Any

property_bp = Blueprint('property', __name__)

@property_bp.route('/extraction/submit', methods=['POST'])
@cross_origin()
def submit_extraction_job():
    """Submit a new property URL for extraction"""
    try:
        data = request.json
        if not data or 'url' not in data:
            return jsonify({'error': 'URL is required'}), 400
        
        url = data['url'].strip()
        
        # Validate URL format
        if not validators.url(url):
            return jsonify({'error': 'Invalid URL format'}), 400
        
        # Optional parameters
        priority = data.get('priority', 'normal').lower()
        strategy = data.get('strategy', 'parallel').lower()
        
        # Validate priority
        priority_mapping = {
            'low': JobPriority.LOW,
            'normal': JobPriority.NORMAL,
            'high': JobPriority.HIGH,
            'urgent': JobPriority.URGENT
        }
        
        if priority not in priority_mapping:
            return jsonify({'error': 'Invalid priority. Must be: low, normal, high, urgent'}), 400
        
        # Validate strategy
        strategy_mapping = {
            'sequential': ExecutionStrategy.SEQUENTIAL,
            'parallel': ExecutionStrategy.PARALLEL,
            'hybrid': ExecutionStrategy.HYBRID
        }
        
        if strategy not in strategy_mapping:
            return jsonify({'error': 'Invalid strategy. Must be: sequential, parallel, hybrid'}), 400
        
        # Check if job already exists for this URL
        existing_job = PropertyExtractionJob.query.filter_by(url=url).first()
        if existing_job and existing_job.status in [ExtractionStatus.PENDING, ExtractionStatus.IN_PROGRESS]:
            return jsonify({
                'message': 'Extraction job already exists for this URL',
                'job_id': existing_job.id,
                'status': existing_job.status.value
            }), 200
        
        # Create new extraction job
        job = PropertyExtractionJob(
            url=url,
            status=ExtractionStatus.PENDING,
            created_at=datetime.utcnow()
        )
        
        db.session.add(job)
        db.session.flush()  # Get the job ID
        
        # Initialize node executions
        node_names = ['node1_basic_info', 'node2_description', 'node3_configuration', 'node4_tenancy']
        for node_name in node_names:
            node_execution = NodeExecution(
                job_id=job.id,
                node_name=node_name,
                status=NodeStatus.PENDING,
                created_at=datetime.utcnow()
            )
            db.session.add(node_execution)
        
        db.session.commit()
        
        # Start progress tracking
        progress_tracker = get_progress_tracker()
        progress_tracker.start_job_tracking(job.id)
        
        # Queue the job for processing
        job_queue = get_job_queue()
        
        # Use asyncio to enqueue the job
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            success = loop.run_until_complete(
                job_queue.enqueue_job(
                    job.id,
                    priority_mapping[priority],
                    strategy_mapping[strategy]
                )
            )
        finally:
            loop.close()
        
        if not success:
            return jsonify({'error': 'Failed to queue job for processing'}), 500
        
        return jsonify({
            'job_id': job.id,
            'status': job.status.value,
            'url': job.url,
            'priority': priority,
            'strategy': strategy,
            'created_at': job.created_at.isoformat(),
            'message': 'Job submitted successfully and queued for processing'
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500

@property_bp.route('/extraction/jobs', methods=['GET'])
@cross_origin()
def get_extraction_jobs():
    """Get list of all extraction jobs with optional filtering"""
    try:
        # Query parameters for filtering
        status = request.args.get('status')
        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)
        
        query = PropertyExtractionJob.query
        
        if status:
            try:
                status_enum = ExtractionStatus(status)
                query = query.filter_by(status=status_enum)
            except ValueError:
                return jsonify({'error': f'Invalid status: {status}'}), 400
        
        jobs = query.order_by(PropertyExtractionJob.created_at.desc()).offset(offset).limit(limit).all()
        
        return jsonify({
            'jobs': [job.to_dict() for job in jobs],
            'total': query.count(),
            'limit': limit,
            'offset': offset
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'Failed to retrieve jobs: {str(e)}'}), 500

@property_bp.route('/extraction/jobs/<int:job_id>', methods=['GET'])
@cross_origin()
def get_extraction_job(job_id):
    """Get detailed information about a specific extraction job"""
    try:
        job = PropertyExtractionJob.query.get_or_404(job_id)
        return jsonify(job.to_dict()), 200
        
    except Exception as e:
        return jsonify({'error': f'Failed to retrieve job: {str(e)}'}), 500

@property_bp.route('/extraction/jobs/<int:job_id>/status', methods=['GET'])
@cross_origin()
def get_job_status(job_id):
    """Get current status and progress of an extraction job"""
    try:
        job = PropertyExtractionJob.query.get_or_404(job_id)
        
        # Get progress from progress tracker
        progress_tracker = get_progress_tracker()
        progress_summary = progress_tracker.get_progress_summary(job_id)
        
        if progress_summary:
            return jsonify(progress_summary), 200
        else:
            # Fallback to basic job status if progress tracking not available
            node_executions = NodeExecution.query.filter_by(job_id=job_id).all()
            
            return jsonify({
                'job_id': job_id,
                'status': job.status.value,
                'overall_progress': calculate_progress_percentage(node_executions),
                'url': job.url,
                'created_at': job.created_at.isoformat(),
                'started_at': job.started_at.isoformat() if job.started_at else None,
                'completed_at': job.completed_at.isoformat() if job.completed_at else None,
                'execution_time': job.extraction_duration,
                'accuracy_score': job.accuracy_score,
                'error_message': job.error_message,
                'node_executions': [
                    {
                        'node_name': ne.node_name,
                        'status': ne.status.value,
                        'started_at': ne.started_at.isoformat() if ne.started_at else None,
                        'completed_at': ne.completed_at.isoformat() if ne.completed_at else None,
                        'execution_duration': ne.execution_duration,
                        'confidence_score': ne.confidence_score,
                        'error_message': ne.error_message
                    }
                    for ne in node_executions
                ]
            }), 200
        
    except Exception as e:
        return jsonify({'error': f'Failed to retrieve job status: {str(e)}'}), 500

@property_bp.route('/extraction/jobs/<int:job_id>/progress', methods=['GET'])
@cross_origin()
def get_job_progress(job_id):
    """Get detailed progress information for a job"""
    try:
        progress_tracker = get_progress_tracker()
        progress = progress_tracker.get_job_progress(job_id)
        
        if not progress:
            return jsonify({'error': 'Job progress not found'}), 404
        
        return jsonify(progress_tracker.get_progress_summary(job_id)), 200
        
    except Exception as e:
        return jsonify({'error': f'Failed to retrieve job progress: {str(e)}'}), 500

@property_bp.route('/extraction/jobs/<int:job_id>/events', methods=['GET'])
@cross_origin()
def get_job_events(job_id):
    """Get progress events for a job"""
    try:
        limit = request.args.get('limit', 50, type=int)
        
        progress_tracker = get_progress_tracker()
        events = progress_tracker.get_job_events(job_id, limit)
        
        return jsonify({
            'job_id': job_id,
            'events': [
                {
                    'event_type': event.event_type.value,
                    'timestamp': event.timestamp.isoformat(),
                    'node_name': event.node_name,
                    'message': event.message,
                    'data': event.data
                }
                for event in events
            ]
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'Failed to retrieve job events: {str(e)}'}), 500

@property_bp.route('/extraction/queue/status', methods=['GET'])
@cross_origin()
def get_queue_status():
    """Get current job queue status"""
    try:
        job_queue = get_job_queue()
        
        # Use asyncio to get queue stats
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            stats = loop.run_until_complete(job_queue.get_queue_stats())
            queued_jobs = loop.run_until_complete(job_queue.get_queued_jobs())
        finally:
            loop.close()
        
        return jsonify({
            'queue_stats': {
                'total_jobs': stats.total_jobs,
                'pending_jobs': stats.pending_jobs,
                'running_jobs': stats.running_jobs,
                'completed_jobs': stats.completed_jobs,
                'failed_jobs': stats.failed_jobs,
                'average_execution_time': stats.average_execution_time,
                'queue_length': stats.queue_length,
                'active_workers': stats.active_workers
            },
            'queued_jobs': queued_jobs
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'Failed to retrieve queue status: {str(e)}'}), 500

def calculate_progress_percentage(node_executions: list) -> int:
    """Calculate progress percentage based on node statuses"""
    if not node_executions:
        return 0
    
    total_nodes = len(node_executions)
    completed_nodes = sum(1 for node in node_executions if node.status == NodeStatus.COMPLETED)
    running_nodes = sum(1 for node in node_executions if node.status == NodeStatus.RUNNING)
    
    # Give partial credit for running nodes
    progress = (completed_nodes + (running_nodes * 0.5)) / total_nodes * 100
    return min(int(progress), 99)  # Cap at 99% until fully completed

