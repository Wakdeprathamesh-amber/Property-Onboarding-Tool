"""
Async orchestration engine for in-memory property extraction.
Manages parallel execution of extraction nodes with dependency handling.
"""

import asyncio
import re
from typing import Dict, List, Optional, Callable, Any
from datetime import datetime
import time

from src.storage.memory_store import (
    get_memory_store, NodeStatus, ExecutionStrategy
)
from src.extraction.gpt_client import GPTExtractionClient
from src.extraction.data_processor import PropertyDataProcessor
from src.utils.logging_config import get_logger
from src.utils.config import get_config

logger = get_logger()

class AsyncOrchestrationEngine:
    """Async orchestration engine for property extraction with in-memory storage"""
    
    def __init__(self):
        self.memory_store = get_memory_store()
        self.gpt_client = GPTExtractionClient()
        self.data_processor = PropertyDataProcessor()
        
        # Define extraction nodes
        self.extraction_nodes = {
            'node_1': {
                'name': 'Basic Info & Location',
                'type': 'basic_info',
                'dependencies': [],
                'weight': 0.25
            },
            'node_2': {
                'name': 'Property Description',
                'type': 'description',
                'dependencies': [],
                'weight': 0.25
            },
            'node_3': {
                'name': 'Room Configurations',
                'type': 'room_configs',
                'dependencies': [],
                'weight': 0.25
            },
            'node_4': {
                'name': 'Tenancy Information',
                'type': 'tenancy_info',
                'dependencies': ['node_1', 'node_3'],  # Depends on basic info and configurations
                'weight': 0.25
            }
        }
    
    async def execute_extraction(self, job_id: str, property_url: str, 
                               execution_strategy: ExecutionStrategy,
                               progress_callback: Optional[Callable] = None) -> Dict[str, Any]:
        """Execute property extraction with specified strategy"""
        try:
            logger.info(f"Starting extraction for job {job_id} with strategy {execution_strategy.value}")
            
            # Create node executions in memory store
            node_executions = {}
            for node_id, node_config in self.extraction_nodes.items():
                node_exec = self.memory_store.create_node_execution(
                    job_id=job_id,
                    node_name=node_config['name'],
                    node_type=node_config['type']
                )
                node_executions[node_id] = node_exec
            
            # Execute based on strategy
            if execution_strategy == ExecutionStrategy.PARALLEL:
                results = await self._execute_parallel(job_id, property_url, node_executions, progress_callback)
            elif execution_strategy == ExecutionStrategy.SEQUENTIAL:
                results = await self._execute_sequential(job_id, property_url, node_executions, progress_callback)
            else:  # HYBRID
                results = await self._execute_hybrid(job_id, property_url, node_executions, progress_callback)
            
            # Enhanced fan-out for Node 4 (Tenancy Information) with improved context
            try:
                # Collect configurations from node 3 if available
                node3 = None
                if 'node_3' in results and results['node_3'].get('success'):
                    node3 = results['node_3'].get('data') or {}
                
                # Look for configurations in both standard location and nested tenancy_data
                configurations = []
                if isinstance(node3, dict):
                    # Check primary configurations array
                    if isinstance(node3.get('configurations'), list):
                        configurations.extend(node3.get('configurations'))
                    # Also check nested configurations in tenancy_data if present
                    if isinstance(node3.get('tenancy_data'), dict) and isinstance(node3.get('tenancy_data').get('configurations'), list):
                        configurations.extend(node3.get('tenancy_data').get('configurations'))
                
                # Deduplicate configurations by name
                seen_names = set()
                unique_configs = []
                for cfg in configurations:
                    if not isinstance(cfg, dict):
                        continue
                    
                    # Try multiple possible name fields
                    cfg_name = None
                    for name_field in ['name', 'Basic.Name', 'room_type', 'Description.Name']:
                        parts = name_field.split('.')
                        current = cfg
                        found = True
                        
                        for part in parts:
                            if isinstance(current, dict) and part in current:
                                current = current[part]
                            else:
                                found = False
                                break
                                
                        if found and current:
                            cfg_name = str(current)
                            break
                    
                    if not cfg_name:
                        cfg_name = f"unnamed_config_{len(unique_configs)+1}"
                    
                    # Normalize name for deduplication
                    norm_name = cfg_name.lower().strip()
                    if norm_name not in seen_names:
                        seen_names.add(norm_name)
                        unique_configs.append((cfg_name, cfg))
                
                if unique_configs:
                    # Create node 4 executions per configuration with enhanced context
                    tenancy_tasks = []
                    
                    # Prepare progress updates
                    if progress_callback:
                        await progress_callback(job_id, {
                            'event_type': 'fan_out_tenancy',
                            'message': f"Extracting tenancy details for {len(unique_configs)} configurations",
                            'progress_percentage': 70.0,
                            'current_phase': 'tenancy_extraction'
                        })
                    
                    # Create and launch tasks for each configuration
                    for idx, (cfg_name, cfg) in enumerate(unique_configs):
                        # Create a clean config key for storage
                        cfg_key = re.sub(r'[^a-zA-Z0-9_]', '_', cfg_name)
                        if not cfg_key:
                            cfg_key = f"config_{idx+1}"
                            
                        # Create node execution
                        node_exec = self.memory_store.create_node_execution(
                            job_id=job_id,
                            node_name=f"Tenancy Information - {cfg_name}",
                            node_type='tenancy_info',
                            config_key=cfg_key
                        )
                        
                        # Enhance context with configuration-specific data
                        enhanced_context = {
                            **results,  # Include all previous results
                            'target_configuration': cfg,  # Add the specific configuration
                            'configuration_name': cfg_name,
                            'configuration_index': idx
                        }
                        
                        # Create task with enhanced context
                        task = asyncio.create_task(
                            self._execute_node(
                                job_id, property_url, 'node_4', self.extraction_nodes['node_4'],
                                node_exec, progress_callback, previous_results=enhanced_context
                            )
                        )
                        tenancy_tasks.append((cfg_key, task))
                    
                    # Process tasks with limited concurrency
                    max_concurrent = 3  # Limit concurrent API calls
                    active_tasks = []
                    remaining_tasks = list(tenancy_tasks)
                    completed_count = 0
                    
                    # Initialize node_4_results dictionary
                    if 'node_4_results' not in results:
                        results['node_4_results'] = {}
                    
                    # Process tasks with controlled concurrency
                    while remaining_tasks or active_tasks:
                        # Start new tasks up to max_concurrent
                        while remaining_tasks and len(active_tasks) < max_concurrent:
                            cfg_key, task = remaining_tasks.pop(0)
                            active_tasks.append((cfg_key, task))
                        
                        # Wait for any task to complete
                        if active_tasks:
                            done, pending = await asyncio.wait(
                                [task for _, task in active_tasks],
                                return_when=asyncio.FIRST_COMPLETED
                            )
                            
                            # Process completed tasks
                            still_active = []
                            for cfg_key, task in active_tasks:
                                if task in done:
                                    try:
                                        res = task.result()
                                        results['node_4_results'][cfg_key] = res
                                        completed_count += 1
                                        
                                        # Update progress
                                        if progress_callback:
                                            progress_pct = 70.0 + (completed_count / len(tenancy_tasks) * 10.0)
                                            await progress_callback(job_id, {
                                                'event_type': 'tenancy_progress',
                                                'message': f"Completed tenancy extraction {completed_count}/{len(tenancy_tasks)}",
                                                'progress_percentage': min(80.0, progress_pct),
                                                'metadata': {'config_key': cfg_key}
                                            })
                                    except Exception as e:
                                        logger.error(f"Error in tenancy extraction for {cfg_key} job {job_id}: {str(e)}")
                                else:
                                    still_active.append((cfg_key, task))
                            
                            # Update active tasks list
                            active_tasks = still_active
                        else:
                            # No active tasks, but this shouldn't happen
                            break
                    
                    logger.info(f"Completed tenancy extraction for {completed_count}/{len(tenancy_tasks)} configurations")
            except Exception as e:
                logger.error(f"Fan-out tenancy error for job {job_id}: {str(e)}")
            
            # Process and merge results
            if progress_callback:
                await progress_callback(job_id, {
                    'event_type': 'merging_data',
                    'message': 'Merging extraction results',
                    'progress_percentage': 80.0,
                    'current_phase': 'merging_data'
                })
            
            merged_data = await self._merge_extraction_results(results)
            
            # Perform competitor analysis only if enabled
            competitor_analysis = {}
            cfg = get_config()
            # Enable competitor analysis by default since we no longer depend on Perplexity
            competitor_enabled = getattr(cfg.extraction, 'enable_competitor_analysis', True)
            
            if competitor_enabled:
                if progress_callback:
                    await progress_callback(job_id, {
                        'event_type': 'competitor_analysis',
                        'message': 'Performing competitor analysis',
                        'progress_percentage': 90.0,
                        'current_phase': 'competitor_analysis'
                    })
                competitor_analysis = await self._perform_competitor_analysis(property_url, merged_data)
            
            # Calculate quality score
            quality_score = self._calculate_quality_score(results, merged_data)
            
            # Final progress update
            if progress_callback:
                await progress_callback(job_id, {
                    'event_type': 'finalizing',
                    'message': 'Finalizing extraction results',
                    'progress_percentage': 95.0,
                    'current_phase': 'finalizing'
                })
            
            return {
                'success': True,
                'extracted_data': results,
                'merged_data': merged_data,
                'competitor_analysis': competitor_analysis,
                'quality_score': quality_score
            }
            
        except Exception as e:
            logger.error(f"Error in extraction execution for job {job_id}: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def _execute_parallel(self, job_id: str, property_url: str, 
                              node_executions: Dict, progress_callback: Optional[Callable]) -> Dict[str, Any]:
        """Execute all nodes in parallel"""
        logger.info(f"Executing parallel extraction for job {job_id}")
        
        # Create tasks for all nodes
        tasks = []
        for node_id, node_config in self.extraction_nodes.items():
            task = asyncio.create_task(
                self._execute_node(
                    job_id, property_url, node_id, node_config, 
                    node_executions[node_id], progress_callback
                )
            )
            tasks.append((node_id, task))
        
        # Wait for all tasks to complete
        results = {}
        for node_id, task in tasks:
            try:
                result = await task
                results[node_id] = result
            except Exception as e:
                logger.error(f"Error in node {node_id} for job {job_id}: {str(e)}")
                results[node_id] = {'success': False, 'error': str(e)}
        
        return results
    
    async def _execute_sequential(self, job_id: str, property_url: str, 
                                node_executions: Dict, progress_callback: Optional[Callable]) -> Dict[str, Any]:
        """Execute nodes sequentially in dependency order"""
        logger.info(f"Executing sequential extraction for job {job_id}")
        
        results = {}
        
        # Execute nodes in dependency order
        execution_order = self._get_execution_order()
        
        for node_id in execution_order:
            node_config = self.extraction_nodes[node_id]
            
            try:
                result = await self._execute_node(
                    job_id, property_url, node_id, node_config, 
                    node_executions[node_id], progress_callback, results
                )
                results[node_id] = result
                
            except Exception as e:
                logger.error(f"Error in node {node_id} for job {job_id}: {str(e)}")
                results[node_id] = {'success': False, 'error': str(e)}
                # Continue with other nodes even if one fails
        
        return results
    
    async def _execute_hybrid(self, job_id: str, property_url: str, 
                            node_executions: Dict, progress_callback: Optional[Callable]) -> Dict[str, Any]:
        """Execute nodes with hybrid strategy (dependencies sequential, independents parallel)"""
        logger.info(f"Executing hybrid extraction for job {job_id}")
        
        results = {}
        
        # First, execute independent nodes in parallel
        independent_nodes = [node_id for node_id, config in self.extraction_nodes.items() 
                           if not config['dependencies']]
        
        if independent_nodes:
            tasks = []
            for node_id in independent_nodes:
                node_config = self.extraction_nodes[node_id]
                task = asyncio.create_task(
                    self._execute_node(
                        job_id, property_url, node_id, node_config, 
                        node_executions[node_id], progress_callback
                    )
                )
                tasks.append((node_id, task))
            
            # Wait for independent nodes
            for node_id, task in tasks:
                try:
                    result = await task
                    results[node_id] = result
                except Exception as e:
                    logger.error(f"Error in node {node_id} for job {job_id}: {str(e)}")
                    results[node_id] = {'success': False, 'error': str(e)}
        
        # Then execute dependent nodes
        dependent_nodes = [node_id for node_id, config in self.extraction_nodes.items() 
                         if config['dependencies']]
        
        for node_id in dependent_nodes:
            node_config = self.extraction_nodes[node_id]
            
            try:
                result = await self._execute_node(
                    job_id, property_url, node_id, node_config, 
                    node_executions[node_id], progress_callback, results
                )
                results[node_id] = result
                
            except Exception as e:
                logger.error(f"Error in node {node_id} for job {job_id}: {str(e)}")
                results[node_id] = {'success': False, 'error': str(e)}
        
        return results
    
    async def _execute_node(self, job_id: str, property_url: str, node_id: str, 
                          node_config: Dict, node_execution, progress_callback: Optional[Callable],
                          previous_results: Optional[Dict] = None) -> Dict[str, Any]:
        """Execute a single extraction node"""
        try:
            logger.info(f"Executing node {node_id} for job {job_id}")
            
            # Update node execution status
            node_execution.status = NodeStatus.RUNNING
            node_execution.start_time = datetime.now()
            self.memory_store.update_node_execution(node_execution)
            
            # Progress update
            if progress_callback:
                await progress_callback(job_id, {
                    'event_type': 'node_started',
                    'message': f"Started {node_config['name']}",
                    'progress_percentage': self._calculate_node_progress(node_id, 'started'),
                    'metadata': {'node_id': node_id, 'node_name': node_config['name']}
                })
            
            # Prepare context from dependencies
            context_data = {}
            if previous_results and node_config['dependencies']:
                for dep_node_id in node_config['dependencies']:
                    if dep_node_id in previous_results and previous_results[dep_node_id].get('success'):
                        context_data[dep_node_id] = previous_results[dep_node_id].get('data', {})
            
            # Execute extraction with retries on common transient failures
            job = self.memory_store.get_job(job_id)
            max_retries = job.max_retries if job else 0
            attempt = 0
            last_error: Optional[Exception] = None
            extracted_data = None
            while attempt <= max_retries:
                try:
                    if node_config['type'] == 'basic_info':
                        extracted_data = await self.gpt_client.extract_basic_info(property_url, context_data)
                    elif node_config['type'] == 'description':
                        extracted_data = await self.gpt_client.extract_description(property_url, context_data)
                    elif node_config['type'] == 'room_configs':
                        extracted_data = await self.gpt_client.extract_room_configurations(property_url, context_data)
                    elif node_config['type'] == 'tenancy_info':
                        extracted_data = await self.gpt_client.extract_tenancy_information(property_url, context_data)
                    else:
                        raise ValueError(f"Unknown node type: {node_config['type']}")
                    break
                except Exception as ex:
                    last_error = ex
                    category = self._categorize_error(str(ex))
                    node_execution.retry_count = attempt
                    node_execution.error_category = category
                    node_execution.error_message = str(ex)
                    self.memory_store.update_node_execution(node_execution)
                    # Retry with exponential backoff for network-related errors
                    if attempt < max_retries and category in {'json_parse', 'timeout', 'network', 'rate_limit', 'connection'}:
                        retry_delay = min(5 * (2 ** attempt), 30)  # Exponential backoff: 5s, 10s, 20s, max 30s
                        logger.warning(f"Retrying {node_config['name']} in {retry_delay}s (attempt {attempt + 1}/{max_retries})")
                        await asyncio.sleep(retry_delay)
                        attempt += 1
                        continue
                    else:
                        raise
            
            # Map node type to validation node name
            validation_node_name = f"node{node_id.split('_')[1]}_{node_config['type']}"
            
            # Validate extracted data
            validation_result = self.data_processor.validate_node_data(extracted_data, validation_node_name, job_id)

            # Use validation completeness as confidence score
            confidence_score = validation_result.completeness_score

            # Attach per-node quality metrics
            node_quality = {
                'completeness': validation_result.completeness_score,
                'errors': len(validation_result.errors),
                'warnings': len(validation_result.warnings),
                'field_scores_present': len(validation_result.field_scores or {}),
            }
            
            # Update node execution with results
            node_execution.status = NodeStatus.COMPLETED
            node_execution.end_time = datetime.now()
            node_execution.execution_time = (node_execution.end_time - node_execution.start_time).total_seconds()
            node_execution.extracted_data = extracted_data
            node_execution.confidence_score = confidence_score
            node_execution.quality_metrics = node_quality
            self.memory_store.update_node_execution(node_execution)
            
            # Progress update
            if progress_callback:
                await progress_callback(job_id, {
                    'event_type': 'node_completed',
                    'message': f"Completed {node_config['name']}",
                    'progress_percentage': self._calculate_node_progress(node_id, 'completed'),
                    'metadata': {
                        'node_id': node_id, 
                        'node_name': node_config['name'],
                        'confidence_score': confidence_score
                    }
                })
            
            logger.info(f"Node {node_id} completed for job {job_id} with confidence {confidence_score}")
            
            return {
                'success': True,
                'data': extracted_data,
                'confidence_score': confidence_score,
                'execution_time': node_execution.execution_time,
                'validation_result': validation_result
            }
            
        except Exception as e:
            logger.error(f"Error executing node {node_id} for job {job_id}: {str(e)}")
            
            # Update node execution with error
            node_execution.status = NodeStatus.FAILED
            node_execution.end_time = datetime.now()
            node_execution.error_message = str(e)
            # Categorize common error types for reporting
            node_execution.error_category = self._categorize_error(str(e))
            if node_execution.start_time:
                node_execution.execution_time = (node_execution.end_time - node_execution.start_time).total_seconds()
            self.memory_store.update_node_execution(node_execution)
            
            # Progress update
            if progress_callback:
                await progress_callback(job_id, {
                    'event_type': 'node_failed',
                    'message': f"Failed {node_config['name']}: {str(e)}",
                    'progress_percentage': self._calculate_node_progress(node_id, 'failed'),
                    'metadata': {'node_id': node_id, 'node_name': node_config['name'], 'error': str(e)}
                })
            
            return {
                'success': False,
                'error': str(e),
                'execution_time': node_execution.execution_time if node_execution.execution_time else 0
            }

    def _categorize_error(self, message: str) -> str:
        """Map common failure messages to categories for easier QA."""
        msg = (message or "").lower()
        if 'timeout' in msg or 'timed out' in msg:
            return 'timeout'
        if 'rate limit' in msg or '429' in msg:
            return 'rate_limit'
        if 'json' in msg and ('parse' in msg or 'unterminated' in msg or 'invalid' in msg):
            return 'json_parse'
        if 'connection' in msg or 'network' in msg:
            return 'network'
        return 'unknown'
    
    def _get_execution_order(self) -> List[str]:
        """Get the correct execution order based on dependencies"""
        ordered = []
        remaining = set(self.extraction_nodes.keys())
        
        while remaining:
            # Find nodes with no unresolved dependencies
            ready = []
            for node_id in remaining:
                dependencies = self.extraction_nodes[node_id]['dependencies']
                if all(dep in ordered for dep in dependencies):
                    ready.append(node_id)
            
            if not ready:
                # Circular dependency or other issue, add remaining nodes
                ready = list(remaining)
            
            # Add ready nodes to order
            for node_id in ready:
                ordered.append(node_id)
                remaining.remove(node_id)
        
        return ordered
    
    def _calculate_node_progress(self, node_id: str, status: str) -> float:
        """Calculate overall progress based on node completion"""
        node_weights = {nid: config['weight'] for nid, config in self.extraction_nodes.items()}
        
        # Base progress before nodes execute
        base_progress = 10.0
        
        # Scale contributions sensibly within 0-100
        if status == 'started':
            return min(100.0, base_progress + (node_weights[node_id] * 20.0))
        elif status == 'completed':
            return min(100.0, base_progress + (node_weights[node_id] * 60.0))
        elif status == 'failed':
            return min(100.0, base_progress + (node_weights[node_id] * 10.0))
        
        return base_progress
    
    async def _merge_extraction_results(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Merge results from all extraction nodes"""
        try:
            # Collect successful extractions
            successful_data = {}
            node_id_to_key = {
                'node_1': 'node1_basic_info',
                'node_2': 'node2_description',
                'node_3': 'node3_configuration',
                'node_4': 'node4_tenancy',
            }
            for node_id, result in results.items():
                if result.get('success') and result.get('data'):
                    key = node_id_to_key.get(node_id, node_id)
                    successful_data[key] = result['data']
            
            # Use data processor to merge
            merge_result = self.data_processor.merge_node_data(successful_data, 0)  # job_id 0 for context calls
            merged_data = merge_result.merged_data if merge_result.success else {}

            # Enhanced tenancy data merging from fanned-out node_4 executions
            try:
                node4_map = results.get('node_4_results') or {}
                if isinstance(node4_map, dict) and merged_data and isinstance(merged_data.get('configurations'), list):
                    # First pass: build a mapping of normalized configuration names to configurations
                    config_map = {}
                    for cfg in merged_data['configurations']:
                        if not isinstance(cfg, dict):
                            continue
                            
                        # Try multiple possible name fields
                        for name_field in ['name', 'Basic.Name', 'room_type', 'Description.Name']:
                            name_parts = name_field.split('.')
                            current = cfg
                            found = True
                            
                            for part in name_parts:
                                if isinstance(current, dict) and part in current:
                                    current = current[part]
                                else:
                                    found = False
                                    break
                                    
                            if found and current:
                                # Normalize name for matching
                                norm_name = str(current).lower().strip()
                                norm_name = re.sub(r'[^a-zA-Z0-9]', '_', norm_name)
                                config_map[norm_name] = cfg
                                # Also store under the original name if different
                                if cfg.get('name') and norm_name != cfg.get('name').lower().strip():
                                    config_map[cfg.get('name').lower().strip()] = cfg
                                break
                    
                    # Second pass: match tenancy data to configurations
                    for cfg_key, node4_result in node4_map.items():
                        if not node4_result or not node4_result.get('success'):
                            continue
                            
                        data = node4_result.get('data') or {}
                        
                        # Try to find matching configuration
                        target_cfg = None
                        
                        # Try direct key match
                        norm_key = cfg_key.lower().strip()
                        norm_key = re.sub(r'[^a-zA-Z0-9]', '_', norm_key)
                        if norm_key in config_map:
                            target_cfg = config_map[norm_key]
                        else:
                            # Try to match by configuration name in the tenancy data
                            cfg_name = data.get('configuration_name') or data.get('name')
                            if cfg_name:
                                norm_name = cfg_name.lower().strip()
                                norm_name = re.sub(r'[^a-zA-Z0-9]', '_', norm_name)
                                if norm_name in config_map:
                                    target_cfg = config_map[norm_name]
                        
                        if target_cfg:
                            # Extract tenancy information from multiple possible locations
                            tenancies = None
                            
                            # Check direct tenancies array
                            if isinstance(data.get('tenancies'), list):
                                tenancies = data.get('tenancies')
                            # Check in configuration.tenancy_options
                            elif isinstance(data.get('configurations'), list) and data['configurations']:
                                for cfg in data['configurations']:
                                    if isinstance(cfg, dict) and isinstance(cfg.get('tenancy_options'), list):
                                        tenancies = cfg.get('tenancy_options')
                                        break
                            
                            # Add tenancies to the target configuration
                            if tenancies and isinstance(tenancies, list):
                                # Ensure target_cfg has a tenancies array
                                if 'tenancies' not in target_cfg:
                                    target_cfg['tenancies'] = []
                                elif not isinstance(target_cfg['tenancies'], list):
                                    target_cfg['tenancies'] = []
                                    
                                # Add new tenancies
                                target_cfg['tenancies'].extend(tenancies)
                                
                                # Deduplicate tenancies by duration
                                if target_cfg['tenancies']:
                                    seen_durations = set()
                                    unique_tenancies = []
                                    
                                    for tenancy in target_cfg['tenancies']:
                                        if not isinstance(tenancy, dict):
                                            continue
                                            
                                        # Get duration as key for deduplication
                                        duration = tenancy.get('tenancy_length') or tenancy.get('duration')
                                        if not duration:
                                            unique_tenancies.append(tenancy)
                                            continue
                                            
                                        duration_key = str(duration).lower().strip()
                                        if duration_key not in seen_durations:
                                            seen_durations.add(duration_key)
                                            unique_tenancies.append(tenancy)
                                    
                                    # Replace with deduplicated list
                                    target_cfg['tenancies'] = unique_tenancies
            except Exception as e:
                logger.error(f"Error merging tenancy data: {str(e)}")
            
            logger.info(f"Merged data from {len(successful_data)} successful nodes")
            return merged_data
            
        except Exception as e:
            logger.error(f"Error merging extraction results: {str(e)}")
            return {}
    
    async def _perform_competitor_analysis(self, property_url: str, merged_data: Dict[str, Any]) -> Dict[str, Any]:
        """Perform competitor analysis using the same enhanced extraction system as property pages"""
        try:
            logger.info("Starting enhanced competitor analysis using GPT extraction client")
            
            # Extract key property information for comparison
            property_name = merged_data.get('property_name', 'Student Accommodation')
            location = merged_data.get('location', {}).get('city', 'Unknown')

            # Get competitor URLs - either from manual input or discovered from property page
            competitor_urls = await self._discover_competitor_urls(property_url, merged_data)
            
            if not competitor_urls:
                logger.info("No competitor URLs found for analysis")
                return {'competitors': [], 'analysis_complete': True, 'message': 'No competitors found'}
            
            # Extract data from competitor URLs using the same enhanced GPT extraction system
            competitor_results = {}
            total_competitors = len(competitor_urls)
            
            logger.info(f"Starting extraction for {total_competitors} competitor URLs")
            
            for idx, competitor_url in enumerate(competitor_urls):
                try:
                    logger.info(f"Analyzing competitor {idx + 1}/{total_competitors}: {competitor_url}")
                    
                    # Use the same GPT extraction client and Node 1-4 extraction as property pages
                    competitor_node_results = {}
                    
                    # Extract Node 1: Basic Info (same enhanced crawling patterns)
                    try:
                        logger.info(f"Extracting Node 1 for competitor {competitor_url}")
                        node1_result = self.gpt_client.extract_property_data(
                            competitor_url, 'node1_basic_info', 0
                        )
                        if node1_result.success:
                            competitor_node_results['node1_basic_info'] = node1_result.data
                            logger.info(f"Node 1 successful for {competitor_url}")
                        else:
                            logger.warning(f"Node 1 failed for competitor {competitor_url}: {node1_result.error}")
                    except Exception as e:
                        logger.error(f"Node 1 extraction error for competitor {competitor_url}: {str(e)}")
                    
                    # Extract Node 2: Description (same enhanced crawling patterns)
                    try:
                        logger.info(f"Extracting Node 2 for competitor {competitor_url}")
                        node2_result = self.gpt_client.extract_property_data(
                            competitor_url, 'node2_description', 0
                        )
                        if node2_result.success:
                            competitor_node_results['node2_description'] = node2_result.data
                            logger.info(f"Node 2 successful for {competitor_url}")
                        else:
                            logger.warning(f"Node 2 failed for competitor {competitor_url}: {node2_result.error}")
                    except Exception as e:
                        logger.error(f"Node 2 extraction error for competitor {competitor_url}: {str(e)}")
                    
                    # Extract Node 3: Configuration (same enhanced crawling patterns + multi-tab/accordion)
                    try:
                        logger.info(f"Extracting Node 3 for competitor {competitor_url}")
                        node3_result = self.gpt_client.extract_property_data(
                            competitor_url, 'node3_configuration', 0
                        )
                        if node3_result.success:
                            competitor_node_results['node3_configuration'] = node3_result.data
                            logger.info(f"Node 3 successful for {competitor_url}")
                        else:
                            logger.warning(f"Node 3 failed for competitor {competitor_url}: {node3_result.error}")
                    except Exception as e:
                        logger.error(f"Node 3 extraction error for competitor {competitor_url}: {str(e)}")
                    
                    # Extract Node 4: Tenancy (same enhanced crawling patterns + multi-tab/accordion)
                    try:
                        logger.info(f"Extracting Node 4 for competitor {competitor_url}")
                        node4_result = self.gpt_client.extract_property_data(
                            competitor_url, 'node4_tenancy', 0
                        )
                        if node4_result.success:
                            competitor_node_results['node4_tenancy'] = node4_result.data
                            logger.info(f"Node 4 successful for {competitor_url}")
                        else:
                            logger.warning(f"Node 4 failed for competitor {competitor_url}: {node4_result.error}")
                    except Exception as e:
                        logger.error(f"Node 4 extraction error for competitor {competitor_url}: {str(e)}")
                    
                    logger.info(f"Completed extraction for {competitor_url}: {len(competitor_node_results)} nodes successful")
                    
                    # Store competitor results with extraction metadata
                    competitor_results[competitor_url] = {
                        'competitor_name': self._extract_competitor_name_from_url(competitor_url),
                        'extraction_results': competitor_node_results,
                        'extraction_success': len(competitor_node_results) > 0,
                        'nodes_extracted': list(competitor_node_results.keys()),
                        'extraction_timestamp': datetime.utcnow().isoformat()
                    }
                    
                    # Add delay between competitor extractions to respect rate limits
                    await asyncio.sleep(2)
                    
                except Exception as e:
                    logger.error(f"Failed to analyze competitor {competitor_url}: {str(e)}")
                    competitor_results[competitor_url] = {
                        'competitor_name': self._extract_competitor_name_from_url(competitor_url),
                        'extraction_results': {},
                        'extraction_success': False,
                        'error': str(e),
                        'extraction_timestamp': datetime.utcnow().isoformat()
                    }
            
            # Calculate analysis summary
            successful_extractions = sum(1 for r in competitor_results.values() if r['extraction_success'])
            total_extractions = len(competitor_results)
            
            analysis_summary = {
                'total_competitors_found': len(competitor_urls),
                'total_competitors_analyzed': total_extractions,
                'successful_extractions': successful_extractions,
                'extraction_success_rate': f"{(successful_extractions/total_extractions*100):.1f}%" if total_extractions > 0 else "0%",
                'analysis_complete': True,
                'analysis_timestamp': datetime.utcnow().isoformat()
            }
            
            logger.info(f"Competitor analysis complete: {successful_extractions}/{total_extractions} successful extractions")
            
            return {
                'competitors': competitor_results,
                'summary': analysis_summary,
                'message': f'Analyzed {total_extractions} competitors using enhanced extraction'
            }
            
        except Exception as e:
            logger.error(f"Error in enhanced competitor analysis: {str(e)}")
            return {
                'error': str(e),
                'competitors': [],
                'analysis_complete': False
            }
    
    async def _discover_competitor_urls(self, property_url: str, merged_data: Dict[str, Any]) -> List[str]:
        """Discover competitor URLs without using external APIs"""
        try:
            logger.info(f"Starting competitor URL discovery for property: {property_url}")
            
            # Option 1: Extract competitor links from the property page itself
            competitor_urls = await self._extract_competitor_links_from_page(property_url)
            logger.info(f"Found {len(competitor_urls)} competitor URLs from page extraction")
            
            # Option 2: Use pre-defined competitor sites if no links found
            if not competitor_urls:
                competitor_urls = self._get_predefined_competitor_sites(merged_data)
                logger.info(f"Using {len(competitor_urls)} predefined competitor sites")
            
            # Option 3: Allow manual competitor URL input (could be added to UI later)
            # This would be implemented in the frontend
            
            final_urls = competitor_urls[:5]  # Limit to 5 competitors for performance
            logger.info(f"Final competitor URLs for analysis: {final_urls}")
            
            return final_urls
            
        except Exception as e:
            logger.error(f"Error discovering competitor URLs: {str(e)}")
            return []
    
    async def _extract_competitor_links_from_page(self, property_url: str) -> List[str]:
        """Extract competitor links from the property page itself"""
        try:
            # Use the scraper to find competitor links on the page
            from src.extraction.scraper import crawl_site, build_context
            
            # Crawl the property page to find competitor links
            pages = crawl_site(
                property_url,
                follow_depth=1,
                max_links_per_page=10,
                max_total_pages=5,
                allow_patterns=[
                    r"competitor|competition|alternative|similar|other|compare|vs|versus",
                    r"homesforstudents|iqstudent|unite-students|freshstudent|studentroost|chapter-living"
                ]
            )
            
            competitor_urls = []
            for page in pages:
                # Look for competitor links in the page content
                if 'competitor' in page.get('url', '').lower() or 'competitor' in page.get('title', '').lower():
                    competitor_urls.append(page['url'])
            
            return list(set(competitor_urls))  # Remove duplicates
            
        except Exception as e:
            logger.error(f"Error extracting competitor links from page: {str(e)}")
            return []
    
    def _get_predefined_competitor_sites(self, merged_data: Dict[str, Any]) -> List[str]:
        """Get pre-defined competitor sites based on location"""
        try:
            location = merged_data.get('location', {}).get('city', '').lower()
            
            # Common competitor sites for student accommodation - use specific city pages
            if 'leeds' in location:
                base_competitor_sites = [
                    "https://www.homesforstudents.com/student-accommodation/leeds",
                    "https://www.iqstudentaccommodation.com/student-accommodation/leeds", 
                    "https://www.unite-students.com/student-accommodation/leeds",
                    "https://www.freshstudentliving.com/student-accommodation/leeds",
                    "https://www.studentroost.co.uk/student-accommodation/leeds"
                ]
            elif 'manchester' in location:
                base_competitor_sites = [
                    "https://www.homesforstudents.com/student-accommodation/manchester",
                    "https://www.iqstudentaccommodation.com/student-accommodation/manchester",
                    "https://www.unite-students.com/student-accommodation/manchester",
                    "https://www.freshstudentliving.com/student-accommodation/manchester",
                    "https://www.studentroost.co.uk/student-accommodation/manchester"
                ]
            elif 'london' in location:
                base_competitor_sites = [
                    "https://www.homesforstudents.com/student-accommodation/london",
                    "https://www.iqstudentaccommodation.com/student-accommodation/london",
                    "https://www.unite-students.com/student-accommodation/london",
                    "https://www.freshstudentliving.com/student-accommodation/london",
                    "https://www.studentroost.co.uk/student-accommodation/london"
                ]
            else:
                # Generic competitor sites
                base_competitor_sites = [
                    "https://www.homesforstudents.com/student-accommodation",
                    "https://www.iqstudentaccommodation.com/student-accommodation", 
                    "https://www.unite-students.com/student-accommodation",
                    "https://www.freshstudentliving.com/student-accommodation",
                    "https://www.studentroost.co.uk/student-accommodation"
                ]
            
            logger.info(f"Using {len(base_competitor_sites)} predefined competitor sites for location: {location}")
            return base_competitor_sites
            
        except Exception as e:
            logger.error(f"Error getting predefined competitor sites: {str(e)}")
            return []
    
    def _extract_competitor_name_from_url(self, url: str) -> str:
        """Extract competitor name from URL for display purposes"""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            
            # Remove www. prefix
            if domain.startswith('www.'):
                domain = domain[4:]
            
            # Map known domains to friendly names
            domain_mapping = {
                'homesforstudents.com': 'Homes for Students',
                'iqstudentaccommodation.com': 'iQ Student Accommodation',
                'unite-students.com': 'Unite Students',
                'freshstudentliving.com': 'Fresh Student Living',
                'studentroost.co.uk': 'Student Roost',
                'chapter-living.com': 'Chapter Living',
                'downtownstudentliving.com': 'Downtown Student Living',
                'amberstudent.com': 'Amber Student',
                'studentuniverse.com': 'Student Universe',
                'accommodationforstudents.com': 'Accommodation for Students'
            }
            
            return domain_mapping.get(domain, domain.replace('.com', '').replace('.co.uk', '').title())
            
        except Exception:
            return "Unknown Competitor"
    
    def _calculate_quality_score(self, results: Dict[str, Any], merged_data: Dict[str, Any]) -> float:
        """Calculate overall quality score for the extraction"""
        try:
            # Collect confidence scores from successful nodes
            confidence_scores = []
            for result in results.values():
                if result.get('success') and result.get('confidence_score') is not None:
                    confidence_scores.append(result['confidence_score'])
            
            if not confidence_scores:
                return 0.0
            
            # Calculate weighted average
            avg_confidence = sum(confidence_scores) / len(confidence_scores)
            
            # Adjust based on data completeness
            completeness_score, _ = self.data_processor._calculate_completeness_with_fields(merged_data)
            
            # Combine confidence and completeness (70% confidence, 30% completeness)
            quality_score = (avg_confidence * 0.7) + (completeness_score * 0.3)
            
            return min(max(quality_score, 0.0), 1.0)  # Clamp between 0 and 1
            
        except Exception as e:
            logger.error(f"Error calculating quality score: {str(e)}")
            return 0.0

