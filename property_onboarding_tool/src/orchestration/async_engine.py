import asyncio
import time
from typing import Dict, Any, List, Optional, Tuple, Callable
from dataclasses import dataclass
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from enum import Enum

from src.models.property import PropertyExtractionJob, NodeExecution, ExtractionStatus, NodeStatus, db
from src.extraction.gpt_client import get_extraction_client, ExtractionResult
from src.extraction.data_processor import get_data_processor
from src.utils.config import get_config
from src.utils.logging_config import get_logger

class ExecutionStrategy(Enum):
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    HYBRID = "hybrid"

@dataclass
class NodeTask:
    """Represents a single node extraction task"""
    node_name: str
    node_execution_id: int
    job_id: int
    url: str
    priority: int = 1
    max_retries: int = 3
    retry_delay: float = 5.0
    timeout: float = 300.0

@dataclass
class OrchestrationResult:
    """Result of orchestration execution"""
    success: bool
    job_id: int
    completed_nodes: List[str]
    failed_nodes: List[str]
    extracted_data: Dict[str, Any]
    merged_data: Optional[Dict[str, Any]]
    execution_time: float
    accuracy_score: float
    error_message: Optional[str]

class AsyncOrchestrationEngine:
    """Advanced async orchestration engine for property extraction"""
    
    def __init__(self):
        self.config = get_config()
        self.logger = get_logger()
        self.extraction_client = get_extraction_client()
        self.data_processor = get_data_processor()
        
        # Execution configuration
        self.max_concurrent_nodes = 4  # Maximum parallel node executions
        self.max_concurrent_jobs = 2   # Maximum parallel job executions
        self.thread_pool = ThreadPoolExecutor(max_workers=8)
        
        # Active job tracking
        self.active_jobs: Dict[int, asyncio.Task] = {}
        self.job_locks: Dict[int, asyncio.Lock] = {}
        
        # Node dependency graph (for future enhancement)
        self.node_dependencies = {
            'node1_basic_info': [],  # No dependencies
            'node2_description': [],  # No dependencies
            'node3_configuration': [],  # No dependencies
            'node4_tenancy': ['node1_basic_info', 'node3_configuration']  # Depends on basic info and configurations
        }
    
    async def orchestrate_extraction(self, job_id: int, strategy: ExecutionStrategy = ExecutionStrategy.PARALLEL) -> OrchestrationResult:
        """Main orchestration method for property extraction"""
        start_time = time.time()
        
        try:
            self.logger.info(f"Starting orchestration for job {job_id} with strategy {strategy.value}", job_id=job_id)
            
            # Get job and validate
            job = await self._get_job_async(job_id)
            if not job:
                return OrchestrationResult(
                    success=False,
                    job_id=job_id,
                    completed_nodes=[],
                    failed_nodes=[],
                    extracted_data={},
                    merged_data=None,
                    execution_time=time.time() - start_time,
                    accuracy_score=0.0,
                    error_message="Job not found"
                )
            
            # Update job status
            await self._update_job_status_async(job_id, ExtractionStatus.IN_PROGRESS)
            
            # Create node tasks
            node_tasks = await self._create_node_tasks(job_id, job.url)
            
            # Execute nodes based on strategy
            if strategy == ExecutionStrategy.PARALLEL:
                node_results = await self._execute_nodes_parallel(node_tasks)
            elif strategy == ExecutionStrategy.SEQUENTIAL:
                node_results = await self._execute_nodes_sequential(node_tasks)
            else:  # HYBRID
                node_results = await self._execute_nodes_hybrid(node_tasks)
            
            # Process results
            completed_nodes = [name for name, result in node_results.items() if result.success]
            failed_nodes = [name for name, result in node_results.items() if not result.success]
            
            # Extract data from successful nodes
            extracted_data = {name: result.data for name, result in node_results.items() if result.success and result.data}
            
            # Merge data if we have successful extractions
            merged_data = None
            accuracy_score = 0.0
            
            if extracted_data:
                merge_result = self.data_processor.merge_node_data(extracted_data, job_id)
                if merge_result.success:
                    merged_data = merge_result.merged_data
                    accuracy_score = merge_result.quality_score
                else:
                    # Use unmerged data with lower accuracy
                    merged_data = extracted_data
                    accuracy_score = 0.5
                
                # Store merged data in job
                await self._store_job_data_async(job_id, extracted_data, merged_data, accuracy_score)
            
            # Perform competitor analysis if enabled
            if (self.config.extraction.enable_competitor_analysis and 
                'node1_basic_info' in extracted_data):
                await self._perform_competitor_analysis_async(job_id, extracted_data)
            
            # Determine final status
            success = len(completed_nodes) > 0
            final_status = ExtractionStatus.COMPLETED if success else ExtractionStatus.FAILED
            error_message = None if success else "All extraction nodes failed"
            
            # Update job status
            execution_time = time.time() - start_time
            await self._finalize_job_async(job_id, final_status, execution_time, accuracy_score, error_message)
            
            self.logger.log_job_complete(job_id, execution_time, accuracy_score)
            
            return OrchestrationResult(
                success=success,
                job_id=job_id,
                completed_nodes=completed_nodes,
                failed_nodes=failed_nodes,
                extracted_data=extracted_data,
                merged_data=merged_data,
                execution_time=execution_time,
                accuracy_score=accuracy_score,
                error_message=error_message
            )
            
        except Exception as e:
            execution_time = time.time() - start_time
            error_message = str(e)
            
            self.logger.error(f"Orchestration failed for job {job_id}: {error_message}", 
                            job_id=job_id, exc_info=True)
            
            # Update job status to failed
            await self._finalize_job_async(job_id, ExtractionStatus.FAILED, execution_time, 0.0, error_message)
            
            return OrchestrationResult(
                success=False,
                job_id=job_id,
                completed_nodes=[],
                failed_nodes=[],
                extracted_data={},
                merged_data=None,
                execution_time=execution_time,
                accuracy_score=0.0,
                error_message=error_message
            )
    
    async def _execute_nodes_parallel(self, node_tasks: List[NodeTask]) -> Dict[str, ExtractionResult]:
        """Execute all nodes in parallel"""
        self.logger.info(f"Executing {len(node_tasks)} nodes in parallel")
        
        # Create semaphore to limit concurrent executions
        semaphore = asyncio.Semaphore(self.max_concurrent_nodes)
        
        # Create tasks for all nodes
        tasks = []
        for node_task in node_tasks:
            task = asyncio.create_task(
                self._execute_single_node_with_semaphore(semaphore, node_task)
            )
            tasks.append((node_task.node_name, task))
        
        # Wait for all tasks to complete
        results = {}
        for node_name, task in tasks:
            try:
                result = await task
                results[node_name] = result
            except Exception as e:
                self.logger.error(f"Node {node_name} execution failed: {str(e)}", exc_info=True)
                results[node_name] = ExtractionResult(
                    success=False,
                    data=None,
                    error=str(e),
                    confidence_score=0.0,
                    execution_time=0.0,
                    raw_response=None
                )
        
        return results
    
    async def _execute_nodes_sequential(self, node_tasks: List[NodeTask]) -> Dict[str, ExtractionResult]:
        """Execute nodes sequentially with dependency handling"""
        self.logger.info(f"Executing {len(node_tasks)} nodes sequentially")
        
        results = {}
        
        # Sort tasks by dependencies and priority
        sorted_tasks = self._sort_tasks_by_dependencies(node_tasks)
        
        for node_task in sorted_tasks:
            try:
                result = await self._execute_single_node(node_task)
                results[node_task.node_name] = result
                
                # If this is a critical dependency and it failed, consider skipping dependent nodes
                if not result.success and self._is_critical_dependency(node_task.node_name):
                    self.logger.warning(f"Critical node {node_task.node_name} failed, may affect dependent nodes")
                
            except Exception as e:
                self.logger.error(f"Node {node_task.node_name} execution failed: {str(e)}", exc_info=True)
                results[node_task.node_name] = ExtractionResult(
                    success=False,
                    data=None,
                    error=str(e),
                    confidence_score=0.0,
                    execution_time=0.0,
                    raw_response=None
                )
        
        return results
    
    async def _execute_nodes_hybrid(self, node_tasks: List[NodeTask]) -> Dict[str, ExtractionResult]:
        """Execute nodes using hybrid strategy (dependencies sequential, independents parallel)"""
        self.logger.info(f"Executing {len(node_tasks)} nodes using hybrid strategy")
        
        results = {}
        
        # Group tasks by dependency level
        dependency_groups = self._group_tasks_by_dependencies(node_tasks)
        
        # Execute each dependency level
        for level, tasks in dependency_groups.items():
            self.logger.info(f"Executing dependency level {level} with {len(tasks)} tasks")
            
            if len(tasks) == 1:
                # Single task - execute directly
                task = tasks[0]
                result = await self._execute_single_node(task)
                results[task.node_name] = result
            else:
                # Multiple tasks - execute in parallel
                level_results = await self._execute_nodes_parallel(tasks)
                results.update(level_results)
        
        return results
    
    async def _execute_single_node_with_semaphore(self, semaphore: asyncio.Semaphore, 
                                                 node_task: NodeTask) -> ExtractionResult:
        """Execute a single node with semaphore control"""
        async with semaphore:
            return await self._execute_single_node(node_task)
    
    async def _execute_single_node(self, node_task: NodeTask) -> ExtractionResult:
        """Execute a single node with retry logic"""
        self.logger.log_node_start(node_task.job_id, node_task.node_name)
        
        # Update node status to running
        await self._update_node_status_async(node_task.node_execution_id, NodeStatus.RUNNING)
        
        last_error = None
        
        for attempt in range(node_task.max_retries + 1):
            try:
                if attempt > 0:
                    self.logger.log_node_retry(node_task.job_id, node_task.node_name, attempt, str(last_error))
                    await asyncio.sleep(node_task.retry_delay * attempt)  # Exponential backoff
                
                # Execute extraction in thread pool to avoid blocking
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    self.thread_pool,
                    self.extraction_client.extract_property_data,
                    node_task.url,
                    node_task.node_name,
                    node_task.job_id
                )
                
                # Update node execution with results
                await self._update_node_execution_async(node_task.node_execution_id, result)
                
                if result.success:
                    self.logger.log_node_complete(
                        node_task.job_id, 
                        node_task.node_name, 
                        result.execution_time,
                        result.confidence_score
                    )
                    return result
                else:
                    last_error = result.error
                    if attempt == node_task.max_retries:
                        self.logger.log_node_failed(
                            node_task.job_id, 
                            node_task.node_name, 
                            result.error,
                            attempt + 1,
                            result.execution_time
                        )
                        await self._update_node_status_async(node_task.node_execution_id, NodeStatus.FAILED)
                        return result
                
            except Exception as e:
                last_error = str(e)
                if attempt == node_task.max_retries:
                    self.logger.log_node_failed(
                        node_task.job_id, 
                        node_task.node_name, 
                        str(e),
                        attempt + 1
                    )
                    await self._update_node_status_async(node_task.node_execution_id, NodeStatus.FAILED)
                    
                    return ExtractionResult(
                        success=False,
                        data=None,
                        error=str(e),
                        confidence_score=0.0,
                        execution_time=0.0,
                        raw_response=None
                    )
        
        # Should not reach here, but just in case
        return ExtractionResult(
            success=False,
            data=None,
            error="Max retries exceeded",
            confidence_score=0.0,
            execution_time=0.0,
            raw_response=None
        )
    
    async def _create_node_tasks(self, job_id: int, url: str) -> List[NodeTask]:
        """Create node tasks for the job"""
        node_executions = await self._get_node_executions_async(job_id)
        
        tasks = []
        for node_execution in node_executions:
            task = NodeTask(
                node_name=node_execution.node_name,
                node_execution_id=node_execution.id,
                job_id=job_id,
                url=url,
                priority=self._get_node_priority(node_execution.node_name),
                max_retries=self.config.extraction.max_retry_attempts,
                retry_delay=self.config.extraction.retry_delay_seconds,
                timeout=self.config.extraction.extraction_timeout_seconds
            )
            tasks.append(task)
        
        return tasks
    
    def _sort_tasks_by_dependencies(self, tasks: List[NodeTask]) -> List[NodeTask]:
        """Sort tasks by dependencies and priority"""
        def dependency_level(node_name: str) -> int:
            if not self.node_dependencies.get(node_name):
                return 0
            return max(dependency_level(dep) for dep in self.node_dependencies[node_name]) + 1
        
        return sorted(tasks, key=lambda t: (dependency_level(t.node_name), -t.priority))
    
    def _group_tasks_by_dependencies(self, tasks: List[NodeTask]) -> Dict[int, List[NodeTask]]:
        """Group tasks by dependency level"""
        groups = {}
        
        for task in tasks:
            level = self._get_dependency_level(task.node_name)
            if level not in groups:
                groups[level] = []
            groups[level].append(task)
        
        return dict(sorted(groups.items()))
    
    def _get_dependency_level(self, node_name: str) -> int:
        """Get dependency level for a node"""
        dependencies = self.node_dependencies.get(node_name, [])
        if not dependencies:
            return 0
        return max(self._get_dependency_level(dep) for dep in dependencies) + 1
    
    def _get_node_priority(self, node_name: str) -> int:
        """Get priority for a node (higher number = higher priority)"""
        priorities = {
            'node1_basic_info': 4,  # Highest priority - needed by other nodes
            'node2_description': 2,
            'node3_configuration': 3,
            'node4_tenancy': 1  # Lowest priority - depends on others
        }
        return priorities.get(node_name, 1)
    
    def _is_critical_dependency(self, node_name: str) -> bool:
        """Check if a node is a critical dependency for others"""
        return node_name in ['node1_basic_info']
    
    async def _perform_competitor_analysis_async(self, job_id: int, extracted_data: Dict[str, Any]):
        """Perform competitor analysis using the same enhanced extraction system as property pages"""
        try:
            if 'node1_basic_info' not in extracted_data:
                return
            
            basic_info = extracted_data['node1_basic_info'].get('basic_info', {})
            location_info = extracted_data['node1_basic_info'].get('location', {})
            
            property_name = basic_info.get('name', '')
            location = location_info.get('location_name', '') or location_info.get('region', '')
            
            if not property_name or not location:
                return
            
            self.logger.info(f"Starting enhanced competitor analysis for job {job_id}", job_id=job_id)
            
            # Get competitor URLs without using external APIs
            competitor_urls = await self._discover_competitor_urls_async(extracted_data, job_id)
            
            if competitor_urls:
                # Analyze competitors using the same enhanced GPT extraction system
                competitor_tasks = []
                for competitor_url in competitor_urls[:3]:  # Limit to top 3 for performance
                    task = asyncio.get_event_loop().run_in_executor(
                        self.thread_pool,
                        self._extract_competitor_data_enhanced,
                        competitor_url,
                        job_id
                    )
                    competitor_tasks.append((competitor_url, task))
                
                # Wait for competitor analyses
                for competitor_url, task in competitor_tasks:
                    try:
                        analysis_result = await task
                        if analysis_result:
                            await self._store_competitor_analysis_async(job_id, analysis_result)
                    except Exception as e:
                        self.logger.warning(f"Competitor analysis failed for {competitor_url}: {str(e)}", 
                                          job_id=job_id)
            else:
                self.logger.info(f"No competitors found for job {job_id}", job_id=job_id)
        
        except Exception as e:
            self.logger.warning(f"Competitor analysis failed: {str(e)}", job_id=job_id)
    
    async def _discover_competitor_urls_async(self, extracted_data: Dict[str, Any], job_id: int) -> List[str]:
        """Discover competitor URLs without using external APIs"""
        try:
            # Option 1: Use pre-defined competitor sites
            competitor_urls = self._get_predefined_competitor_sites(extracted_data)
            
            # Option 2: Extract competitor links from the property page itself (if we have the URL)
            # This would require storing the original property URL in the job
            
            # Option 3: Allow manual competitor URL input (could be added to UI later)
            
            return competitor_urls[:5]  # Limit to 5 competitors for performance
            
        except Exception as e:
            self.logger.error(f"Error discovering competitor URLs: {str(e)}", job_id=job_id)
            return []
    
    def _get_predefined_competitor_sites(self, extracted_data: Dict[str, Any]) -> List[str]:
        """Get pre-defined competitor sites based on location"""
        try:
            location_info = extracted_data.get('node1_basic_info', {}).get('location', {})
            location = location_info.get('location_name', '') or location_info.get('region', '')
            
            # Common competitor sites for student accommodation
            base_competitor_sites = [
                "https://www.homesforstudents.com",
                "https://www.iqstudentaccommodation.com", 
                "https://www.unite-students.com",
                "https://www.freshstudentliving.com",
                "https://www.studentroost.co.uk",
                "https://www.chapter-living.com"
            ]
            
            # If we have location info, we could customize the search
            # For now, return base sites
            return base_competitor_sites
            
        except Exception as e:
            self.logger.error(f"Error getting predefined competitor sites: {str(e)}")
            return []
    
    def _extract_competitor_data_enhanced(self, competitor_url: str, job_id: int) -> Optional[Dict[str, Any]]:
        """Extract competitor data using the same enhanced GPT extraction system as property pages"""
        try:
            self.logger.info(f"Extracting competitor data from {competitor_url}", job_id=job_id)
            
            # Use the same GPT extraction client and Node 1-4 extraction as property pages
            competitor_node_results = {}
            
            # Extract Node 1: Basic Info (same enhanced crawling patterns)
            try:
                node1_result = self.extraction_client.extract_property_data(
                    competitor_url, 'node1_basic_info', job_id
                )
                if node1_result.success:
                    competitor_node_results['node1_basic_info'] = node1_result.data
                else:
                    self.logger.warning(f"Node 1 failed for competitor {competitor_url}: {node1_result.error}", job_id=job_id)
            except Exception as e:
                self.logger.error(f"Node 1 extraction error for competitor {competitor_url}: {str(e)}", job_id=job_id)
            
            # Extract Node 2: Description (same enhanced crawling patterns)
            try:
                node2_result = self.extraction_client.extract_property_data(
                    competitor_url, 'node2_description', job_id
                )
                if node2_result.success:
                    competitor_node_results['node2_description'] = node2_result.data
                else:
                    self.logger.warning(f"Node 2 failed for competitor {competitor_url}: {node2_result.error}", job_id=job_id)
            except Exception as e:
                self.logger.error(f"Node 2 extraction error for competitor {competitor_url}: {str(e)}", job_id=job_id)
            
            # Extract Node 3: Configuration (same enhanced crawling patterns + multi-tab/accordion)
            try:
                node3_result = self.extraction_client.extract_property_data(
                    competitor_url, 'node3_configuration', job_id
                )
                if node3_result.success:
                    competitor_node_results['node3_configuration'] = node3_result.data
                else:
                    self.logger.warning(f"Node 3 failed for competitor {competitor_url}: {node3_result.error}", job_id=job_id)
            except Exception as e:
                self.logger.error(f"Node 3 extraction error for competitor {competitor_url}: {str(e)}", job_id=job_id)
            
            # Extract Node 4: Tenancy (same enhanced crawling patterns + multi-tab/accordion)
            try:
                node4_result = self.extraction_client.extract_property_data(
                    competitor_url, 'node4_tenancy', job_id
                )
                if node4_result.success:
                    competitor_node_results['node4_tenancy'] = node4_result.data
                else:
                    self.logger.warning(f"Node 4 failed for competitor {competitor_url}: {node3_result.error}", job_id=job_id)
            except Exception as e:
                self.logger.error(f"Node 4 extraction error for competitor {competitor_url}: {str(e)}", job_id=job_id)
            
            # Return competitor results with extraction metadata
            if competitor_node_results:
                return {
                    'competitor_url': competitor_url,
                    'competitor_name': self._extract_competitor_name_from_url(competitor_url),
                    'extraction_results': competitor_node_results,
                    'extraction_success': True,
                    'nodes_extracted': list(competitor_node_results.keys()),
                    'extraction_timestamp': datetime.utcnow().isoformat()
                }
            else:
                return {
                    'competitor_url': competitor_url,
                    'competitor_name': self._extract_competitor_name_from_url(competitor_url),
                    'extraction_results': {},
                    'extraction_success': False,
                    'error': 'No nodes successfully extracted',
                    'extraction_timestamp': datetime.utcnow().isoformat()
                }
                
        except Exception as e:
            self.logger.error(f"Failed to extract competitor data from {competitor_url}: {str(e)}", job_id=job_id)
            return {
                'competitor_url': competitor_url,
                'competitor_name': self._extract_competitor_name_from_url(competitor_url),
                'extraction_results': {},
                'extraction_success': False,
                'error': str(e),
                'extraction_timestamp': datetime.utcnow().isoformat()
            }
    
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
    
    # Async database operations
    async def _get_job_async(self, job_id: int) -> Optional[PropertyExtractionJob]:
        """Get job asynchronously"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: PropertyExtractionJob.query.get(job_id)
        )
    
    async def _get_node_executions_async(self, job_id: int) -> List[NodeExecution]:
        """Get node executions asynchronously"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: NodeExecution.query.filter_by(job_id=job_id).all()
        )
    
    async def _update_job_status_async(self, job_id: int, status: ExtractionStatus):
        """Update job status asynchronously"""
        def update_status():
            job = PropertyExtractionJob.query.get(job_id)
            if job:
                job.status = status
                if status == ExtractionStatus.IN_PROGRESS:
                    job.started_at = datetime.utcnow()
                db.session.commit()
        
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, update_status)
    
    async def _update_node_status_async(self, node_execution_id: int, status: NodeStatus):
        """Update node execution status asynchronously"""
        def update_status():
            node = NodeExecution.query.get(node_execution_id)
            if node:
                node.status = status
                if status == NodeStatus.RUNNING:
                    node.started_at = datetime.utcnow()
                elif status in [NodeStatus.COMPLETED, NodeStatus.FAILED]:
                    node.completed_at = datetime.utcnow()
                db.session.commit()
        
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, update_status)
    
    async def _update_node_execution_async(self, node_execution_id: int, result: ExtractionResult):
        """Update node execution with results asynchronously"""
        def update_execution():
            node = NodeExecution.query.get(node_execution_id)
            if node:
                node.execution_duration = result.execution_time
                node.raw_response = result.raw_response
                node.completed_at = datetime.utcnow()
                
                if result.success:
                    node.status = NodeStatus.COMPLETED
                    node.set_extracted_data(result.data)
                    node.confidence_score = result.confidence_score
                else:
                    node.status = NodeStatus.FAILED
                    node.error_message = result.error
                
                db.session.commit()
        
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, update_execution)
    
    async def _store_job_data_async(self, job_id: int, extracted_data: Dict[str, Any], 
                                  merged_data: Dict[str, Any], accuracy_score: float):
        """Store job data asynchronously"""
        def store_data():
            job = PropertyExtractionJob.query.get(job_id)
            if job:
                # Store individual node data
                if 'node1_basic_info' in extracted_data:
                    job.set_basic_info_data(extracted_data['node1_basic_info'])
                if 'node2_description' in extracted_data:
                    job.set_description_data(extracted_data['node2_description'])
                if 'node3_configuration' in extracted_data:
                    job.set_configuration_data(extracted_data['node3_configuration'])
                if 'node4_tenancy' in extracted_data:
                    job.set_tenancy_data(extracted_data['node4_tenancy'])
                
                # Store merged data
                job.set_merged_data(merged_data)
                job.accuracy_score = accuracy_score
                
                db.session.commit()
        
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, store_data)
    
    async def _store_competitor_analysis_async(self, job_id: int, analysis_result):
        """Store competitor analysis asynchronously"""
        def store_analysis():
            from src.models.property import CompetitorAnalysis
            
            competitor_analysis = CompetitorAnalysis(
                job_id=job_id,
                competitor_url=analysis_result['competitor_url'],
                competitor_name=analysis_result['competitor_name'],
                similarity_score=analysis_result['similarity_score'] # Assuming similarity_score is part of analysis_result
            )
            competitor_analysis.set_extracted_data(analysis_result['extraction_results'])
            
            db.session.add(competitor_analysis)
            db.session.commit()
        
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, store_analysis)
    
    async def _finalize_job_async(self, job_id: int, status: ExtractionStatus, 
                                execution_time: float, accuracy_score: float, 
                                error_message: Optional[str]):
        """Finalize job asynchronously"""
        def finalize():
            job = PropertyExtractionJob.query.get(job_id)
            if job:
                job.status = status
                job.completed_at = datetime.utcnow()
                job.extraction_duration = execution_time
                job.accuracy_score = accuracy_score
                if error_message:
                    job.error_message = error_message
                db.session.commit()
        
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, finalize)
    
    def cleanup(self):
        """Cleanup resources"""
        if self.thread_pool:
            self.thread_pool.shutdown(wait=True)

# Global orchestration engine instance
_orchestration_engine = None

def get_orchestration_engine() -> AsyncOrchestrationEngine:
    """Get the global orchestration engine instance"""
    global _orchestration_engine
    if _orchestration_engine is None:
        _orchestration_engine = AsyncOrchestrationEngine()
    return _orchestration_engine

