"""
Property extraction routes using in-memory storage.
Handles property URL submission, job management, and result retrieval.
"""

from flask import Blueprint, request, jsonify
from typing import Dict, Any, List
from src.storage.memory_store import (
    get_memory_store, JobStatus, JobPriority, ExecutionStrategy
)
from src.orchestration.async_engine_memory import AsyncOrchestrationEngine
from src.orchestration.job_queue_memory import get_job_queue
from src.utils.logging_config import get_logger
from src.utils.validation import PropertyDataValidator
import asyncio
from datetime import datetime
from urllib.parse import urlparse
import csv
import io
from src.extraction.gpt_client import GPTExtractionClient
from src.extraction.data_processor import PropertyDataProcessor
import os

property_bp = Blueprint('property', __name__)
logger = get_logger()

@property_bp.route('/test/validation', methods=['POST'])
def test_validation():
    """Test endpoint for debugging validation issues"""
    try:
        data = request.get_json()
        logger.info(f"Test validation received: {data}")
        
        if not data or 'url' not in data:
            return jsonify({'error': 'Missing URL in test data'}), 400
        
        test_url = data['url']
        
        # Test URL validation
        from src.utils.validation import PropertyDataValidator
        is_valid, error = PropertyDataValidator.validate_url(test_url)
        
        return jsonify({
            'url': test_url,
            'is_valid': is_valid,
            'error': error,
            'url_parsed': {
                'scheme': urlparse(test_url).scheme if test_url else None,
                'netloc': urlparse(test_url).netloc if test_url else None,
                'path': urlparse(test_url).path if test_url else None
            }
        })
        
    except Exception as e:
        logger.error(f"Test validation error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@property_bp.route('/extraction/submit', methods=['POST'])
def submit_extraction_job():
    """Submit a new property extraction job"""
    try:
        data = request.get_json()
        
        # Debug logging
        logger.info(f"Received data: {data}")
        
        # Validate required fields
        if not data or 'property_url' not in data:
            logger.error(f"Missing property_url in data: {data}")
            return jsonify({
                'error': 'Missing required field: property_url'
            }), 400
        
        property_url = data['property_url']
        priority = data.get('priority', 'normal')
        execution_strategy = data.get('execution_strategy', 'parallel')
        
        logger.info(f"Processing URL: {property_url}, Priority: {priority}, Strategy: {execution_strategy}")
        
        # Validate inputs
        is_valid_url, url_error = PropertyDataValidator.validate_url(property_url)
        if not is_valid_url:
            logger.error(f"URL validation failed: {url_error} for URL: {property_url}")
            return jsonify({
                'error': f'Invalid property URL: {url_error}',
                'url_received': property_url
            }), 400
        
        if priority.lower() not in ['low', 'normal', 'high', 'urgent']:
            return jsonify({
                'error': 'Invalid priority. Must be one of: low, normal, high, urgent'
            }), 400
        
        if execution_strategy.lower() not in ['parallel', 'sequential', 'hybrid']:
            return jsonify({
                'error': 'Invalid execution strategy. Must be one of: parallel, sequential, hybrid'
            }), 400
        
        # Convert string values to enums
        priority_enum = JobPriority(priority.lower())
        strategy_enum = ExecutionStrategy(execution_strategy.lower())
        
        # Create job in memory store
        memory_store = get_memory_store()
        job = memory_store.create_job(
            property_url=property_url,
            priority=priority_enum,
            execution_strategy=strategy_enum
        )
        
        # Add to processing queue
        memory_store.enqueue_job(job.id)
        
        # Log job submission
        logger.info(f"Property extraction job submitted: {job.id} for URL: {property_url}")
        
        # Add initial progress event
        memory_store.add_progress_event(
            job_id=job.id,
            event_type="job_submitted",
            message="Job submitted successfully",
            progress_percentage=0.0
        )
        
        return jsonify({
            'job_id': job.id,
            'status': job.status.value,
            'property_url': job.property_url,
            'priority': job.priority.value,
            'execution_strategy': job.execution_strategy.value,
            'created_at': job.created_at.isoformat(),
            'message': 'Job submitted successfully'
        }), 201
        
    except Exception as e:
        logger.error(f"Error submitting extraction job: {str(e)}")
        return jsonify({
            'error': 'Internal server error',
            'details': str(e)
        }), 500

@property_bp.route('/extraction/jobs', methods=['GET'])
def list_extraction_jobs():
    """List all extraction jobs with optional filtering"""
    try:
        # Get query parameters
        status_filter = request.args.get('status')
        priority_filter = request.args.get('priority')
        limit = request.args.get('limit', type=int)
        
        # Validate filters
        status_enum = None
        if status_filter:
            try:
                status_enum = JobStatus(status_filter.lower())
            except ValueError:
                return jsonify({
                    'error': 'Invalid status filter'
                }), 400
        
        priority_enum = None
        if priority_filter:
            try:
                priority_enum = JobPriority(priority_filter.lower())
            except ValueError:
                return jsonify({
                    'error': 'Invalid priority filter'
                }), 400
        
        # Get jobs from memory store
        memory_store = get_memory_store()
        jobs = memory_store.get_all_jobs(status=status_enum, priority=priority_enum)
        
        # Apply limit if specified
        if limit and limit > 0:
            jobs = jobs[:limit]
        
        # Convert to response format
        jobs_data = []
        for job in jobs:
            jobs_data.append({
                'job_id': job.id,
                'property_url': job.property_url,
                'status': job.status.value,
                'priority': job.priority.value,
                'execution_strategy': job.execution_strategy.value,
                'progress_percentage': job.progress_percentage,
                'current_phase': job.current_phase,
                'created_at': job.created_at.isoformat(),
                'updated_at': job.updated_at.isoformat(),
                'start_time': job.start_time.isoformat() if job.start_time else None,
                'end_time': job.end_time.isoformat() if job.end_time else None,
                'execution_time': job.execution_time,
                'quality_score': job.quality_score,
                'error_message': job.error_message
            })
        
        return jsonify({
            'jobs': jobs_data,
            'total_count': len(jobs_data)
        }), 200
        
    except Exception as e:
        logger.error(f"Error listing extraction jobs: {str(e)}")
        return jsonify({
            'error': 'Internal server error',
            'details': str(e)
        }), 500

@property_bp.route('/extraction/jobs/<job_id>', methods=['GET'])
def get_extraction_job(job_id):
    """Get detailed information about a specific extraction job"""
    try:
        memory_store = get_memory_store()
        job = memory_store.get_job(job_id)
        
        if not job:
            return jsonify({
                'error': 'Job not found'
            }), 404
        
        # Get node executions
        node_executions = memory_store.get_node_executions_for_job(job_id)

        # Convert node executions to response format (list, legacy)
        nodes_data = []
        for node_exec in node_executions:
            nodes_data.append({
                'node_id': node_exec.id,
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
                'error_category': node_exec.error_category
            })

        # Build node_results map expected by UI tabs
        node_type_to_key = {
            'basic_info': 'node1_basic_info',
            'description': 'node2_description',
            'room_configs': 'node3_configuration',
            'tenancy_info': 'node4_tenancy',
        }
        node_results = {}
        for node_exec in node_executions:
            key = node_type_to_key.get(node_exec.node_type)
            if not key:
                continue
            # Map status 'running' -> 'in_progress' to match UI
            status_value = node_exec.status.value
            if status_value == 'running':
                status_value = 'in_progress'
            node_results[key] = {
                'status': status_value,
                'confidence_score': node_exec.confidence_score,
                'execution_duration': node_exec.execution_time,
                'data_completeness': node_exec.confidence_score,
                'quality_metrics': node_exec.quality_metrics,
                'data': node_exec.extracted_data,
            }
        
        return jsonify({
            'job_id': job.id,
            'property_url': job.property_url,
            'url': job.property_url,
            'status': job.status.value,
            'priority': job.priority.value,
            'execution_strategy': job.execution_strategy.value,
            'progress_percentage': job.progress_percentage,
            'current_phase': job.current_phase,
            'created_at': job.created_at.isoformat(),
            'updated_at': job.updated_at.isoformat(),
            'start_time': job.start_time.isoformat() if job.start_time else None,
            'end_time': job.end_time.isoformat() if job.end_time else None,
            'execution_time': job.execution_time,
            'extraction_duration': job.execution_time,
            'extracted_data': job.extracted_data,
            'merged_data': job.merged_data,
            'competitor_analysis': job.competitor_analysis,
            'competitor_analyses': job.competitor_analysis if isinstance(job.competitor_analysis, list) else [],
            'quality_score': job.quality_score,
            'accuracy_score': job.quality_score,
            'completed_at': job.end_time.isoformat() if job.end_time else None,
            'error_message': job.error_message,
            'retry_count': job.retry_count,
            'max_retries': job.max_retries,
            'node_executions': nodes_data,
            'node_results': node_results
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting extraction job {job_id}: {str(e)}")
        return jsonify({
            'error': 'Internal server error',
            'details': str(e)
        }), 500

@property_bp.route('/extraction/jobs/<job_id>/export', methods=['GET'])
def export_job_results(job_id):
    """Export job results as JSON or CSV. Query param format=json|csv (default json)."""
    try:
        export_format = request.args.get('format', 'json').lower()
        memory_store = get_memory_store()
        job = memory_store.get_job(job_id)
        if not job:
            return jsonify({'error': 'Job not found'}), 404

        if export_format == 'csv':
            # Flatten merged_data to rows for CSV (configurations + tenancies)
            rows = _flatten_for_csv(job.merged_data or {})
            if not rows:
                rows = []
            # Build CSV in-memory
            output = io.StringIO()
            fieldnames = sorted({k for r in rows for k in r.keys()}) or ['note']
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()
            for r in rows:
                writer.writerow(r)
            csv_data = output.getvalue()
            output.close()
            return (csv_data, 200, {
                'Content-Type': 'text/csv; charset=utf-8',
                'Content-Disposition': f'attachment; filename="job_{job_id}.csv"'
            })
        else:
            # Default JSON export
            return jsonify({
                'job_id': job.id,
                'property_url': job.property_url,
                'merged_data': job.merged_data,
                'quality_score': job.quality_score
            }), 200
    except Exception as e:
        logger.error(f"Error exporting job {job_id}: {str(e)}")
        return jsonify({'error': 'Internal server error', 'details': str(e)}), 500

@property_bp.route('/extraction/jobs/<job_id>/export/csv', methods=['GET'])
def export_job_results_csv(job_id):
    """Export extraction job results as CSV"""
    try:
        memory_store = get_memory_store()
        job = memory_store.get_job(job_id)
        
        if not job:
            return jsonify({
                'error': 'Job not found'
            }), 404
        
        if job.status != JobStatus.COMPLETED:
            return jsonify({
                'error': 'Job not completed yet',
                'current_status': job.status.value,
                'progress_percentage': job.progress_percentage
            }), 400
        
        # Get node executions for detailed results
        node_executions = memory_store.get_node_executions_for_job(job_id)
        
        if not node_executions:
            return jsonify({
                'error': 'No node execution data found'
            }), 404
        
        # Collect all node data
        node_data = {}
        for node_exec in node_executions:
            if node_exec.result and node_exec.result.get('success'):
                node_name = node_exec.node_name
                node_data[node_name] = node_exec.result.get('data', {})
        
        if not node_data:
            return jsonify({
                'error': 'No successful node data found'
            }), 404
        
        # Generate CSV data
        csv_data = generate_property_csv(node_data, job)
        
        # Create CSV response
        from io import StringIO
        output = StringIO()
        writer = csv.writer(output)
        
        # Write CSV data
        for row in csv_data:
            writer.writerow(row)
        
        output.seek(0)
        
        # Generate filename
        property_name = "property"
        if 'Basic Info & Location' in node_data:
            basic_info = node_data['Basic Info & Location'].get('basic_info', {})
            if basic_info.get('name'):
                property_name = basic_info['name'].replace(' ', '_').replace('/', '_')[:50]
        
        filename = f"{property_name}_{job_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
        
        from flask import Response
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={'Content-Disposition': f'attachment; filename={filename}'}
        )
        
    except Exception as e:
        logger.error(f"Error exporting job {job_id} to CSV: {str(e)}")
        return jsonify({
            'error': 'Internal server error',
            'details': str(e)
        }), 500

@property_bp.route('/competitors/compare', methods=['POST'])
def compare_competitor():
    """Extract both links with the same pipeline and return JSON for each (no stats).
    Body: { "property_url": str, "competitor_url": str }
    """
    try:
        data = request.get_json() or {}
        prop_url = data.get('property_url')
        comp_url = data.get('competitor_url')
        if not prop_url or not comp_url:
            return jsonify({'error': 'property_url and competitor_url are required'}), 400

        logger.info(f"/competitors/compare called property_url={prop_url} competitor_url={comp_url}")
        # Quick runtime config check
        has_api_key = bool(os.environ.get('OPENAI_API_KEY'))
        logger.info(f"Config check: OPENAI_API_KEY set={has_api_key}")

        client = GPTExtractionClient()
        processor = PropertyDataProcessor()

        def extract_all(url: str) -> Dict[str, Any]:
            results: Dict[str, Any] = {
                'node_results': {},
                'node_status': {},
                'errors': []
            }
            for node_type in ['node1_basic_info', 'node2_description', 'node3_configuration', 'node4_tenancy']:
                try:
                    r = client.extract_property_data(url, node_type, job_id=0)
                    results['node_status'][node_type] = {
                        'success': bool(getattr(r, 'success', False)),
                        'error_category': getattr(r, 'error_category', None)
                    }
                    if getattr(r, 'success', False) and getattr(r, 'data', None):
                        results['node_results'][node_type] = r.data
                    else:
                        err_msg = getattr(r, 'error', None) or getattr(r, 'message', None) or 'unknown_error'
                        if err_msg:
                            results['errors'].append({ 'node': node_type, 'message': str(err_msg) })
                        logger.warning(f"Extraction failed for {node_type} url={url} error={err_msg}")
                except Exception as ex:
                    logger.error(f"Extraction exception for node {node_type} url={url} error={str(ex)}")
                    results['errors'].append({ 'node': node_type, 'message': str(ex) })

            merged = processor.merge_node_data(results['node_results'], job_id=0)
            results['merged_data'] = merged.merged_data if getattr(merged, 'success', False) else results['node_results']
            results['any_success'] = any(v.get('success') for v in results['node_status'].values())
            return results

        ours = extract_all(prop_url)
        theirs = extract_all(comp_url)

        # If both sides failed entirely, return a 502 with diagnostic info
        if not ours.get('any_success') and not theirs.get('any_success'):
            logger.error(f"Compare failed for both URLs. property_url={prop_url} competitor_url={comp_url} errors_our={ours.get('errors')} errors_theirs={theirs.get('errors')}")
            return jsonify({
                'error': 'Extraction failed for both URLs',
                'property_url': prop_url,
                'competitor_url': comp_url,
                'our_errors': ours.get('errors'),
                'their_errors': theirs.get('errors')
            }), 502

        return jsonify({
            'success': True,
            'property_url': prop_url,
            'competitor_url': comp_url,
            'our': ours,
            'competitor': theirs
        }), 200
    except Exception as e:
        logger.error(f"Compare competitor failed: {str(e)}")
        return jsonify({'error': 'Internal server error', 'details': str(e)}), 500

@property_bp.route('/competitors/compare/export/csv', methods=['POST'])
def export_competitor_comparison_csv():
    """Export competitor comparison results as CSV"""
    try:
        data = request.get_json() or {}
        prop_url = data.get('property_url')
        comp_url = data.get('competitor_url')
        
        if not prop_url or not comp_url:
            return jsonify({'error': 'property_url and competitor_url are required'}), 400

        client = GPTExtractionClient()
        processor = PropertyDataProcessor()

        def extract_all(url: str) -> Dict[str, Any]:
            n1 = client.extract_property_data(url, 'node1_basic_info', job_id=0)
            n2 = client.extract_property_data(url, 'node2_description', job_id=0)
            n3 = client.extract_property_data(url, 'node3_configuration', job_id=0)
            n4 = client.extract_property_data(url, 'node4_tenancy', job_id=0)
            node_results = {}
            if n1.success and n1.data:
                node_results['node1_basic_info'] = n1.data
            if n2.success and n2.data:
                node_results['node2_description'] = n2.data
            if n3.success and n3.data:
                node_results['node3_configuration'] = n3.data
            if n4.success and n4.data:
                node_results['node4_tenancy'] = n4.data
            merged = processor.merge_node_data(node_results, job_id=0)
            return {
                'node_results': node_results,
                'merged_data': merged.merged_data if merged.success else node_results
            }

        ours = extract_all(prop_url)
        theirs = extract_all(comp_url)
        
        # Generate comparison CSV
        csv_data = generate_comparison_csv(ours, theirs, prop_url, comp_url)
        
        # Create CSV response
        from io import StringIO
        output = StringIO()
        writer = csv.writer(output)
        
        # Write CSV data
        for row in csv_data:
            writer.writerow(row)
        
        output.seek(0)
        
        # Generate filename
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        filename = f"competitor_comparison_{timestamp}.csv"
        
        from flask import Response
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={'Content-Disposition': f'attachment; filename={filename}'}
        )
        
    except Exception as e:
        logger.error(f"Error exporting competitor comparison to CSV: {str(e)}")
        return jsonify({'error': 'Internal server error', 'details': str(e)}), 500

def _flatten_for_csv(merged: dict) -> list[dict]:
    """Flatten merged_data into row dicts for CSV: one row per configuration x tenancy (or config if no tenancy)."""
    rows: list[dict] = []
    if not isinstance(merged, dict):
        return rows

    basic = merged.get('basic_info', {}) if isinstance(merged.get('basic_info'), dict) else {}
    location = merged.get('location', {}) if isinstance(merged.get('location'), dict) else {}
    configs = merged.get('configurations', []) if isinstance(merged.get('configurations'), list) else []

    base = {
        'property_name': basic.get('name') or basic.get('property_name') or '',
        'source': basic.get('source', ''),
        'source_link': basic.get('source_link', ''),
        'city': location.get('city', ''),
        'country': location.get('country', ''),
    }

    if not configs:
        rows.append(base)
        return rows

    for cfg in configs:
        cfg_name = cfg.get('name') or cfg.get('Basic', {}).get('Configuration Name', '')
        cfg_row = base | {
            'configuration_name': cfg_name,
        }
        tenancies = cfg.get('tenancies') if isinstance(cfg.get('tenancies'), list) else []
        if not tenancies:
            rows.append(cfg_row)
            continue
        for t in tenancies:
            row = cfg_row.copy()
            if isinstance(t, dict):
                for k, v in t.items():
                    row[f'tenancy.{k}'] = v
            rows.append(row)
    return rows

def generate_property_csv(node_data: Dict[str, Any], job) -> List[List[str]]:
    """Generate CSV data for property extraction results"""
    csv_rows = []
    
    # Header row
    csv_rows.append([
        'Property Information',
        'Field',
        'Value',
        'Source Node',
        'Extraction Time'
    ])
    
    # Basic Info & Location
    if 'Basic Info & Location' in node_data:
        basic_info = node_data['Basic Info & Location']
        
        # Basic property info
        if 'basic_info' in basic_info:
            info = basic_info['basic_info']
            csv_rows.extend([
                ['Property', 'Name', info.get('name', ''), 'Basic Info', job.created_at.strftime('%Y-%m-%d %H:%M:%S')],
                ['Property', 'Type', info.get('property_type', ''), 'Basic Info', ''],
                ['Property', 'Source', info.get('source', ''), 'Basic Info', ''],
                ['Property', 'Source Link', info.get('source_link', ''), 'Basic Info', ''],
                ['Property', 'Guarantor Required', info.get('guarantor_required', ''), 'Basic Info', '']
            ])
        
        # Location info
        if 'location' in basic_info:
            location = basic_info['location']
            csv_rows.extend([
                ['Location', 'Name', location.get('location_name', ''), 'Basic Info', ''],
                ['Location', 'Address', location.get('address', ''), 'Basic Info', ''],
                ['Location', 'City', location.get('city', ''), 'Basic Info', ''],
                ['Location', 'Region', location.get('region', ''), 'Basic Info', ''],
                ['Location', 'Country', location.get('country', ''), 'Basic Info', ''],
                ['Location', 'Postcode', location.get('postcode', ''), 'Basic Info', ''],
                ['Location', 'Latitude', location.get('latitude', ''), 'Basic Info', ''],
                ['Location', 'Longitude', location.get('longitude', ''), 'Basic Info', '']
            ])
        
        # Features
        if 'features' in basic_info and basic_info['features']:
            for i, feature in enumerate(basic_info['features']):
                if isinstance(feature, dict):
                    csv_rows.append([
                        'Features', 
                        f'Feature {i+1}', 
                        feature.get('name', str(feature)), 
                        'Basic Info', 
                        ''
                    ])
                else:
                    csv_rows.append([
                        'Features', 
                        f'Feature {i+1}', 
                        str(feature), 
                        'Basic Info', 
                        ''
                    ])
    
    # Property Description
    if 'Property Description' in node_data:
        desc = node_data['Property Description']
        if 'description' in desc:
            description = desc['description']
            
            # About section
            csv_rows.append(['Description', 'About', description.get('about', ''), 'Property Description', ''])
            
            # Highlights
            if 'highlights' in description and description['highlights']:
                for i, highlight in enumerate(description['highlights']):
                    csv_rows.append([
                        'Description', 
                        f'Highlight {i+1}', 
                        str(highlight), 
                        'Property Description', 
                        ''
                    ])
            
            # FAQs
            if 'faqs' in description and description['faqs']:
                for i, faq in enumerate(description['faqs']):
                    if isinstance(faq, dict):
                        csv_rows.append([
                            'FAQs', 
                            f'Q{i+1}', 
                            faq.get('question', ''), 
                            'Property Description', 
                            ''
                        ])
                        csv_rows.append([
                            'FAQs', 
                            f'A{i+1}', 
                            faq.get('answer', ''), 
                            'Property Description', 
                            ''
                        ])
            
            # Payments
            if 'payments' in description:
                payments = description['payments']
                csv_rows.extend([
                    ['Payments', 'Booking Deposit', payments.get('booking_deposit', ''), 'Property Description', ''],
                    ['Payments', 'Security Deposit', payments.get('security_deposit', ''), 'Property Description', ''],
                    ['Payments', 'Mode of Payment', payments.get('mode_of_payment', ''), 'Property Description', ''],
                    ['Payments', 'Installments', payments.get('payment_installment_plan', ''), 'Property Description', '']
                ])
    
    # Room Configurations
    if 'Room Configurations' in node_data:
        configs = node_data['Room Configurations']
        if 'configurations' in configs and configs['configurations']:
            for i, config in enumerate(configs['configurations']):
                if isinstance(config, dict):
                    # Basic config info
                    csv_rows.extend([
                        [f'Configuration {i+1}', 'Name', config.get('Basic', {}).get('Name', ''), 'Room Configurations', ''],
                        [f'Configuration {i+1}', 'Status', config.get('Basic', {}).get('Status', ''), 'Room Configurations', ''],
                        [f'Configuration {i+1}', 'Min Price', config.get('Pricing', {}).get('Min Price', ''), 'Room Configurations', ''],
                        [f'Configuration {i+1}', 'Max Price', config.get('Pricing', {}).get('Max Price', ''), 'Room Configurations', ''],
                        [f'Configuration {i+1}', 'Bedroom Count', config.get('Configuration', {}).get('Bedroom Count', ''), 'Room Configurations', ''],
                        [f'Configuration {i+1}', 'Bathroom Count', config.get('Configuration', {}).get('Bathroom Count', ''), 'Room Configurations', '']
                    ])
                    
                    # Features
                    if 'Features' in config and config['Features']:
                        for j, feature in enumerate(config['Features']):
                            if isinstance(feature, dict):
                                csv_rows.append([
                                    f'Configuration {i+1}', 
                                    f'Feature {j+1}', 
                                    feature.get('Description', str(feature)), 
                                    'Room Configurations', 
                                    ''
                                ])
    
    # Tenancy Information
    if 'Tenancy Information' in node_data:
        tenancy = node_data['Tenancy Information']
        if 'configurations' in tenancy and tenancy['configurations']:
            for i, config in enumerate(tenancy['configurations']):
                if isinstance(config, dict):
                    # Basic tenancy info
                    csv_rows.extend([
                        [f'Tenancy {i+1}', 'Name', config.get('name', ''), 'Tenancy Information', ''],
                        [f'Tenancy {i+1}', 'Status', config.get('status', ''), 'Tenancy Information', ''],
                        [f'Tenancy {i+1}', 'Base Price', config.get('base_price', ''), 'Tenancy Information', ''],
                        [f'Tenancy {i+1}', 'Room Type', config.get('room_type', ''), 'Tenancy Information', '']
                    ])
                    
                    # Tenancy options
                    if 'tenancy_options' in config and config['tenancy_options']:
                        for j, option in enumerate(config['tenancy_options']):
                            if isinstance(option, dict):
                                csv_rows.extend([
                                    [f'Tenancy {i+1} Option {j+1}', 'Length', option.get('tenancy_length', ''), 'Tenancy Information', ''],
                                    [f'Tenancy {i+1} Option {j+1}', 'Price', option.get('price', ''), 'Tenancy Information', ''],
                                    [f'Tenancy {i+1} Option {j+1}', 'Start Date', option.get('start_date', ''), 'Tenancy Information', ''],
                                    [f'Tenancy {i+1} Option {j+1}', 'End Date', option.get('end_date', ''), 'Tenancy Information', '']
                                ])
    
    return csv_rows

def generate_comparison_csv(ours: Dict[str, Any], theirs: Dict[str, Any], 
                           prop_url: str, comp_url: str) -> List[List[str]]:
    """Generate CSV data for competitor comparison"""
    csv_rows = []
    
    # Header row
    csv_rows.append([
        'Category',
        'Field',
        'Our Property',
        'Competitor Property',
        'Difference',
        'Notes'
    ])
    
    # Basic Information Comparison
    our_basic = ours.get('merged_data', {}).get('basic_info', {})
    their_basic = theirs.get('merged_data', {}).get('basic_info', {})
    
    csv_rows.extend([
        ['Basic Info', 'Property Name', our_basic.get('name', ''), their_basic.get('name', ''), '', ''],
        ['Basic Info', 'Property Type', our_basic.get('property_type', ''), their_basic.get('property_type', ''), '', ''],
        ['Basic Info', 'Source', our_basic.get('source', ''), their_basic.get('source', ''), '', '']
    ])
    
    # Location Comparison
    our_location = ours.get('merged_data', {}).get('location', {})
    their_location = theirs.get('merged_data', {}).get('location', {})
    
    csv_rows.extend([
        ['Location', 'City', our_location.get('city', ''), their_location.get('city', ''), '', ''],
        ['Location', 'Region', our_location.get('region', ''), their_location.get('region', ''), '', ''],
        ['Location', 'Country', our_location.get('country', ''), their_location.get('country', ''), '', '']
    ])
    
    # Pricing Comparison
    our_configs = ours.get('merged_data', {}).get('configurations', [])
    their_configs = theirs.get('merged_data', {}).get('configurations', [])
    
    # Find minimum and maximum prices
    our_prices = []
    their_prices = []
    
    for config in our_configs:
        if isinstance(config, dict) and 'Pricing' in config:
            pricing = config['Pricing']
            if pricing.get('Min Price'):
                try:
                    price = float(str(pricing['Min Price']).replace('£', '').replace(',', ''))
                    our_prices.append(price)
                except:
                    pass
    
    for config in their_configs:
        if isinstance(config, dict) and 'Pricing' in config:
            pricing = config['Pricing']
            if pricing.get('Min Price'):
                try:
                    price = float(str(pricing['Min Price']).replace('£', '').replace(',', ''))
                    their_prices.append(price)
                except:
                    pass
    
    if our_prices and their_prices:
        our_min = min(our_prices)
        our_max = max(our_prices)
        their_min = min(their_prices)
        their_max = max(their_prices)
        
        csv_rows.extend([
            ['Pricing', 'Min Price', f'£{our_min}', f'£{their_min}', f'£{our_min - their_min}', ''],
            ['Pricing', 'Max Price', f'£{our_max}', f'£{their_max}', f'£{our_max - their_max}', '']
        ])
    
    # Features Comparison
    our_features = ours.get('merged_data', {}).get('features', [])
    their_features = theirs.get('merged_data', {}).get('features', [])
    
    # Convert features to sets for comparison
    our_feature_set = set()
    their_feature_set = set()
    
    for feature in our_features:
        if isinstance(feature, dict):
            our_feature_set.add(feature.get('name', str(feature)).lower())
        else:
            our_feature_set.add(str(feature).lower())
    
    for feature in their_features:
        if isinstance(feature, dict):
            their_feature_set.add(feature.get('name', str(feature)).lower())
        else:
            their_feature_set.add(str(feature).lower())
    
    # Unique to us
    unique_to_us = our_feature_set - their_feature_set
    for feature in list(unique_to_us)[:10]:  # Limit to 10 features
        csv_rows.append(['Features', 'Unique to Us', feature, '', '', ''])
    
    # Unique to them
    unique_to_them = their_feature_set - our_feature_set
    for feature in list(unique_to_them)[:10]:  # Limit to 10 features
        csv_rows.append(['Features', 'Unique to Them', '', feature, '', ''])
    
    # Shared features
    shared_features = our_feature_set & their_feature_set
    for feature in list(shared_features)[:10]:  # Limit to 10 features
        csv_rows.append(['Features', 'Shared', feature, feature, '', ''])
    
    # Room Configuration Comparison
    csv_rows.append(['Room Configs', 'Count', str(len(our_configs)), str(len(their_configs)), '', ''])
    
    # Tenancy Options Comparison
    our_tenancy = ours.get('merged_data', {}).get('tenancy_data', {})
    their_tenancy = theirs.get('merged_data', {}).get('tenancy_data', {})
    
    if 'configurations' in our_tenancy and 'configurations' in their_tenancy:
        our_tenancy_count = len(our_tenancy['configurations'])
        their_tenancy_count = len(their_tenancy['configurations'])
        csv_rows.append(['Tenancy Options', 'Count', str(our_tenancy_count), str(their_tenancy_count), '', ''])
    
    return csv_rows

@property_bp.route('/extraction/jobs/<job_id>/status', methods=['GET'])
def get_job_status(job_id):
    """Get the current status of an extraction job"""
    try:
        memory_store = get_memory_store()
        job = memory_store.get_job(job_id)
        
        if not job:
            return jsonify({
                'error': 'Job not found'
            }), 404
        
        return jsonify({
            'job_id': job.id,
            'status': job.status.value,
            'progress_percentage': job.progress_percentage,
            'current_phase': job.current_phase,
            'updated_at': job.updated_at.isoformat(),
            'error_message': job.error_message
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting job status {job_id}: {str(e)}")
        return jsonify({
            'error': 'Internal server error',
            'details': str(e)
        }), 500

@property_bp.route('/extraction/jobs/<job_id>/results', methods=['GET'])
def get_job_results(job_id):
    """Get the extraction results for a completed job"""
    try:
        memory_store = get_memory_store()
        job = memory_store.get_job(job_id)
        
        if not job:
            return jsonify({
                'error': 'Job not found'
            }), 404
        
        if job.status != JobStatus.COMPLETED:
            return jsonify({
                'error': 'Job not completed yet',
                'current_status': job.status.value,
                'progress_percentage': job.progress_percentage
            }), 400
        
        # Get node executions for detailed results
        node_executions = memory_store.get_node_executions_for_job(job_id)
        
        # Organize results by node
        node_results = {}
        for node_exec in node_executions:
            node_results[node_exec.node_name] = {
                'status': node_exec.status.value,
                'extracted_data': node_exec.extracted_data,
                'confidence_score': node_exec.confidence_score,
                'execution_time': node_exec.execution_time,
                'quality_metrics': node_exec.quality_metrics,
                'error_category': node_exec.error_category,
                'config_key': node_exec.config_key
            }
        
        return jsonify({
            'job_id': job.id,
            'property_url': job.property_url,
            'status': job.status.value,
            'execution_time': job.execution_time,
            'quality_score': job.quality_score,
            'merged_data': job.merged_data,
            'competitor_analysis': job.competitor_analysis,
            'node_results': node_results,
            'completed_at': job.end_time.isoformat() if job.end_time else None
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting job results {job_id}: {str(e)}")
        return jsonify({
            'error': 'Internal server error',
            'details': str(e)
        }), 500

@property_bp.route('/extraction/jobs/<job_id>/progress', methods=['GET'])
def get_job_progress(job_id):
    """Get detailed progress information for a job"""
    try:
        memory_store = get_memory_store()
        job = memory_store.get_job(job_id)
        
        if not job:
            return jsonify({
                'error': 'Job not found'
            }), 404
        
        # Get progress events
        progress_events = memory_store.get_progress_events(job_id)
        
        # Get node executions for node-level progress
        node_executions = memory_store.get_node_executions_for_job(job_id)
        
        # Convert events to response format
        events_data = []
        for event in progress_events:
            # Lift node_name to top-level if present in metadata for UI convenience
            node_name = None
            if event.metadata and isinstance(event.metadata, dict):
                node_name = event.metadata.get('node_name')
            events_data.append({
                'event_id': event.id,
                'event_type': event.event_type,
                'message': event.message,
                'progress_percentage': event.progress_percentage,
                'timestamp': event.timestamp.isoformat(),
                'metadata': event.metadata,
                'node_name': node_name
            })
        
        # Build node details map expected by UI
        node_details = {}
        nodes_completed = 0
        nodes_failed = 0
        for idx, node_exec in enumerate(node_executions, start=1):
            # Map statuses to UI-friendly values
            status = node_exec.status.value
            if status == 'running':
                status = 'in_progress'
            progress_pct = 0.0
            if node_exec.status.value == 'completed':
                progress_pct = 100.0
                nodes_completed += 1
            elif node_exec.status.value == 'running':
                progress_pct = 50.0
            elif node_exec.status.value == 'failed':
                nodes_failed += 1
            
            key = f"node_{idx}"
            node_details[key] = {
                'status': status,
                'progress': progress_pct,
                'execution_time': node_exec.execution_time,
                'confidence_score': node_exec.confidence_score,
                'error': node_exec.error_message,
            }
        
        # Compute overall progress if not already high
        overall_progress = job.progress_percentage or 0.0
        if node_executions:
            avg_nodes = sum(v['progress'] for v in node_details.values()) / (len(node_details) or 1)
            overall_progress = max(overall_progress, avg_nodes * 0.6 / 1.0 + 10.0)  # keep >10 after start
            overall_progress = min(100.0, round(overall_progress, 1))
        
        # Map top-level status to UI-friendly values
        status_value = job.status.value
        if status_value == 'running':
            status_value = 'in_progress'
        
        return jsonify({
            'job_id': job.id,
            'overall_progress': overall_progress,
            'current_phase': job.current_phase,
            'status': status_value,
            'events': events_data,
            'node_details': node_details,
            'nodes_completed': nodes_completed,
            'nodes_failed': nodes_failed,
            'execution_time': job.execution_time,
            'accuracy_score': job.quality_score,
            'updated_at': job.updated_at.isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting job progress {job_id}: {str(e)}")
        return jsonify({
            'error': 'Internal server error',
            'details': str(e)
        }), 500

@property_bp.route('/extraction/jobs/<job_id>/events', methods=['GET'])
def get_job_events(job_id):
    """Get progress events for a job"""
    try:
        # Get query parameters
        limit = request.args.get('limit', 50, type=int)
        
        memory_store = get_memory_store()
        job = memory_store.get_job(job_id)
        
        if not job:
            return jsonify({
                'error': f'Job not found: {job_id}'
            }), 404
        
        # Get progress events
        progress_events = memory_store.get_progress_events(job_id)
        
        # Limit events if requested
        if limit and len(progress_events) > limit:
            progress_events = progress_events[-limit:]
        
        # Convert events to response format
        events_data = []
        for event in progress_events:
            events_data.append({
                'id': event.id,
                'job_id': event.job_id,
                'event_type': event.event_type,
                'message': event.message,
                'progress_percentage': event.progress_percentage,
                'timestamp': event.timestamp.isoformat(),
                'metadata': event.metadata
            })
        
        return jsonify({
            'job_id': job_id,
            'events': events_data,
            'total_events': len(progress_events)
        })
        
    except Exception as e:
        logger.error(f"Error getting job events: {str(e)}")
        return jsonify({
            'error': 'Internal server error',
            'details': str(e)
        }), 500

@property_bp.route('/extraction/jobs/<job_id>/cancel', methods=['POST'])
def cancel_extraction_job(job_id):
    """Cancel a running or pending extraction job"""
    try:
        memory_store = get_memory_store()
        job = memory_store.get_job(job_id)
        
        if not job:
            return jsonify({
                'error': 'Job not found'
            }), 404
        
        if job.status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
            return jsonify({
                'error': f'Cannot cancel job with status: {job.status.value}'
            }), 400
        
        # Update job status
        job.status = JobStatus.CANCELLED
        job.end_time = datetime.now()
        memory_store.update_job(job)
        
        # Add progress event
        memory_store.add_progress_event(
            job_id=job_id,
            event_type="job_cancelled",
            message="Job cancelled by user request",
            progress_percentage=job.progress_percentage
        )
        
        logger.info(f"Extraction job cancelled: {job_id}")
        
        return jsonify({
            'job_id': job_id,
            'status': job.status.value,
            'message': 'Job cancelled successfully'
        }), 200
        
    except Exception as e:
        logger.error(f"Error cancelling job {job_id}: {str(e)}")
        return jsonify({
            'error': 'Internal server error',
            'details': str(e)
        }), 500

@property_bp.route('/extraction/jobs/<job_id>/retry', methods=['POST'])
def retry_extraction_job(job_id):
    """Retry a failed extraction job"""
    try:
        memory_store = get_memory_store()
        job = memory_store.get_job(job_id)
        
        if not job:
            return jsonify({
                'error': 'Job not found'
            }), 404
        
        if job.status != JobStatus.FAILED:
            return jsonify({
                'error': f'Cannot retry job with status: {job.status.value}'
            }), 400
        
        if job.retry_count >= job.max_retries:
            return jsonify({
                'error': 'Maximum retry attempts exceeded'
            }), 400
        
        # Reset job for retry
        job.status = JobStatus.PENDING
        job.retry_count += 1
        job.start_time = None
        job.end_time = None
        job.execution_time = None
        job.error_message = None
        job.progress_percentage = 0.0
        job.current_phase = "initializing"
        memory_store.update_job(job)
        
        # Re-enqueue the job
        memory_store.enqueue_job(job_id)
        
        # Add progress event
        memory_store.add_progress_event(
            job_id=job_id,
            event_type="job_retried",
            message=f"Job retry attempt {job.retry_count}/{job.max_retries}",
            progress_percentage=0.0
        )
        
        logger.info(f"Extraction job retried: {job_id} (attempt {job.retry_count})")
        
        return jsonify({
            'job_id': job_id,
            'status': job.status.value,
            'retry_count': job.retry_count,
            'max_retries': job.max_retries,
            'message': 'Job queued for retry'
        }), 200
        
    except Exception as e:
        logger.error(f"Error retrying job {job_id}: {str(e)}")
        return jsonify({
            'error': 'Internal server error',
            'details': str(e)
        }), 500

@property_bp.route('/extraction/stats', methods=['GET'])
def get_extraction_stats():
    """Get overall extraction system statistics"""
    try:
        memory_store = get_memory_store()
        stats = memory_store.get_queue_stats()
        
        return jsonify({
            'total_jobs': stats.total_jobs,
            'active_workers': stats.active_workers,
            'queue_length': stats.queue_length,
            'running_jobs': stats.running_jobs,
            'completed_jobs': stats.completed_jobs,
            'failed_jobs': stats.failed_jobs,
            'system_status': 'healthy'
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting extraction stats: {str(e)}")
        return jsonify({
            'error': 'Internal server error',
            'details': str(e)
        }), 500

@property_bp.route('/extraction/queue/status', methods=['GET'])
def get_queue_status():
    """Get current job queue status"""
    try:
        # Get job queue instance
        job_queue = get_job_queue()
        
        # Use asyncio to get queue stats
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            stats = loop.run_until_complete(job_queue.get_queue_stats())
            queue_info = {
                'active_workers': stats.active_workers,
                'queue_length': stats.queue_length,
                'running_jobs': stats.running_jobs,
                'is_processing': stats.active_workers > 0 or stats.running_jobs > 0
            }
        finally:
            loop.close()
        
        return jsonify(queue_info), 200
        
    except Exception as e:
        logger.error(f"Error getting queue status: {str(e)}")
        return jsonify({
            'error': 'Internal server error',
            'details': str(e)
        }), 500

