import logging
import logging.handlers
import os
from datetime import datetime
from typing import Optional

class PropertyExtractionLogger:
    """Custom logger for property extraction operations"""
    
    def __init__(self, name: str = "property_extraction"):
        self.logger = logging.getLogger(name)
        self._setup_logger()
    
    def _setup_logger(self):
        """Setup logger with appropriate handlers and formatters"""
        if self.logger.handlers:
            return  # Already configured
        
        self.logger.setLevel(logging.INFO)
        
        # Create logs directory if it doesn't exist
        log_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'logs')
        os.makedirs(log_dir, exist_ok=True)
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)
        
        # File handler for general logs
        file_handler = logging.handlers.RotatingFileHandler(
            os.path.join(log_dir, 'property_extraction.log'),
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5
        )
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
        )
        file_handler.setFormatter(file_formatter)
        self.logger.addHandler(file_handler)
        
        # Separate handler for extraction operations
        extraction_handler = logging.handlers.RotatingFileHandler(
            os.path.join(log_dir, 'extractions.log'),
            maxBytes=50*1024*1024,  # 50MB
            backupCount=10
        )
        extraction_handler.setLevel(logging.INFO)
        extraction_formatter = logging.Formatter(
            '%(asctime)s - JOB_%(job_id)s - NODE_%(node_name)s - %(levelname)s - %(message)s'
        )
        extraction_handler.setFormatter(extraction_formatter)
        
        # Create a filter to only log extraction-related messages to this handler
        extraction_handler.addFilter(lambda record: hasattr(record, 'job_id'))
        self.logger.addHandler(extraction_handler)
        
        # Error handler for critical issues
        error_handler = logging.handlers.RotatingFileHandler(
            os.path.join(log_dir, 'errors.log'),
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5
        )
        error_handler.setLevel(logging.ERROR)
        error_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s\n%(exc_info)s'
        )
        error_handler.setFormatter(error_formatter)
        self.logger.addHandler(error_handler)
    
    def log_job_start(self, job_id: int, url: str):
        """Log the start of an extraction job"""
        extra = {'job_id': job_id, 'node_name': 'SYSTEM'}
        self.logger.info(f"Starting extraction job for URL: {url}", extra=extra)
    
    def log_job_complete(self, job_id: int, duration: float, accuracy_score: Optional[float] = None):
        """Log the completion of an extraction job"""
        extra = {'job_id': job_id, 'node_name': 'SYSTEM'}
        message = f"Extraction job completed in {duration:.2f} seconds"
        if accuracy_score is not None:
            message += f" with accuracy score: {accuracy_score:.3f}"
        self.logger.info(message, extra=extra)
    
    def log_job_failed(self, job_id: int, error: str, duration: Optional[float] = None):
        """Log the failure of an extraction job"""
        extra = {'job_id': job_id, 'node_name': 'SYSTEM'}
        message = f"Extraction job failed: {error}"
        if duration is not None:
            message += f" (failed after {duration:.2f} seconds)"
        self.logger.error(message, extra=extra)
    
    def log_node_start(self, job_id: int, node_name: str):
        """Log the start of a node execution"""
        extra = {'job_id': job_id, 'node_name': node_name}
        self.logger.info(f"Starting node execution", extra=extra)
    
    def log_node_complete(self, job_id: int, node_name: str, duration: float, 
                         confidence_score: Optional[float] = None, 
                         data_completeness: Optional[float] = None):
        """Log the completion of a node execution"""
        extra = {'job_id': job_id, 'node_name': node_name}
        message = f"Node execution completed in {duration:.2f} seconds"
        if confidence_score is not None:
            message += f", confidence: {confidence_score:.3f}"
        if data_completeness is not None:
            message += f", completeness: {data_completeness:.3f}"
        self.logger.info(message, extra=extra)
    
    def log_node_failed(self, job_id: int, node_name: str, error: str, 
                       retry_count: int = 0, duration: Optional[float] = None):
        """Log the failure of a node execution"""
        extra = {'job_id': job_id, 'node_name': node_name}
        message = f"Node execution failed: {error}"
        if retry_count > 0:
            message += f" (retry #{retry_count})"
        if duration is not None:
            message += f" (failed after {duration:.2f} seconds)"
        self.logger.error(message, extra=extra)
    
    def log_node_retry(self, job_id: int, node_name: str, retry_count: int, reason: str):
        """Log a node execution retry"""
        extra = {'job_id': job_id, 'node_name': node_name}
        self.logger.warning(f"Retrying node execution (attempt #{retry_count}): {reason}", extra=extra)
    
    def log_api_call(self, job_id: int, node_name: str, api_name: str, 
                    duration: float, success: bool, error: Optional[str] = None):
        """Log an API call"""
        extra = {'job_id': job_id, 'node_name': node_name}
        if success:
            self.logger.info(f"{api_name} API call successful in {duration:.2f} seconds", extra=extra)
        else:
            self.logger.error(f"{api_name} API call failed in {duration:.2f} seconds: {error}", extra=extra)
    
    def log_data_merge(self, job_id: int, conflicts_found: int, conflicts_resolved: int):
        """Log data merging operation"""
        extra = {'job_id': job_id, 'node_name': 'MERGE'}
        message = f"Data merge completed. Conflicts found: {conflicts_found}, resolved: {conflicts_resolved}"
        self.logger.info(message, extra=extra)
    
    def log_competitor_analysis(self, job_id: int, competitor_url: str, 
                              similarity_score: Optional[float] = None, success: bool = True):
        """Log competitor analysis operation"""
        extra = {'job_id': job_id, 'node_name': 'COMPETITOR'}
        if success:
            message = f"Competitor analysis completed for {competitor_url}"
            if similarity_score is not None:
                message += f" (similarity: {similarity_score:.3f})"
            self.logger.info(message, extra=extra)
        else:
            self.logger.error(f"Competitor analysis failed for {competitor_url}", extra=extra)
    
    def debug(self, message: str, job_id: Optional[int] = None, node_name: Optional[str] = None):
        """Log debug message"""
        extra = {}
        if job_id is not None:
            extra['job_id'] = job_id
        # Ensure node_name is always present when job_id is present to satisfy formatter
        if node_name is None and job_id is not None:
            extra['node_name'] = 'SYSTEM'
        elif node_name is not None:
            extra['node_name'] = node_name
        self.logger.debug(message, extra=extra)
    
    def info(self, message: str, job_id: Optional[int] = None, node_name: Optional[str] = None):
        """Log info message"""
        extra = {}
        if job_id is not None:
            extra['job_id'] = job_id
        # Ensure node_name is always present when job_id is present to satisfy formatter
        if node_name is None and job_id is not None:
            extra['node_name'] = 'SYSTEM'
        elif node_name is not None:
            extra['node_name'] = node_name
        self.logger.info(message, extra=extra)
    
    def warning(self, message: str, job_id: Optional[int] = None, node_name: Optional[str] = None):
        """Log warning message"""
        extra = {}
        if job_id is not None:
            extra['job_id'] = job_id
        # Ensure node_name is always present when job_id is present to satisfy formatter
        if node_name is None and job_id is not None:
            extra['node_name'] = 'SYSTEM'
        elif node_name is not None:
            extra['node_name'] = node_name
        self.logger.warning(message, extra=extra)
    
    def error(self, message: str, job_id: Optional[int] = None, node_name: Optional[str] = None, exc_info=None):
        """Log error message"""
        extra = {}
        if job_id is not None:
            extra['job_id'] = job_id
        # Ensure node_name is always present when job_id is present to satisfy formatter
        if node_name is None and job_id is not None:
            extra['node_name'] = 'SYSTEM'
        elif node_name is not None:
            extra['node_name'] = node_name
        self.logger.error(message, extra=extra, exc_info=exc_info)

# Global logger instance
extraction_logger = PropertyExtractionLogger()

def get_logger() -> PropertyExtractionLogger:
    """Get the global extraction logger instance"""
    return extraction_logger

def setup_flask_logging(app):
    """Setup Flask application logging"""
    if not app.debug:
        # In production, log to file
        log_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'logs')
        os.makedirs(log_dir, exist_ok=True)
        
        file_handler = logging.handlers.RotatingFileHandler(
            os.path.join(log_dir, 'flask_app.log'),
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5
        )
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        app.logger.setLevel(logging.INFO)
        app.logger.info('Property Onboarding Tool startup')

