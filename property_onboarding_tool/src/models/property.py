from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import json
from enum import Enum

db = SQLAlchemy()

class ExtractionStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class NodeStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"

class PropertyExtractionJob(db.Model):
    """Main table for tracking property extraction jobs"""
    __tablename__ = 'property_extraction_jobs'
    
    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.Text, nullable=False)
    status = db.Column(db.Enum(ExtractionStatus), default=ExtractionStatus.PENDING, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    error_message = db.Column(db.Text)
    
    # Extracted data storage
    basic_info_data = db.Column(db.Text)  # JSON string
    description_data = db.Column(db.Text)  # JSON string
    configuration_data = db.Column(db.Text)  # JSON string
    tenancy_data = db.Column(db.Text)  # JSON string
    merged_data = db.Column(db.Text)  # JSON string - final merged result
    
    # Metadata
    extraction_duration = db.Column(db.Float)  # Duration in seconds
    accuracy_score = db.Column(db.Float)  # Quality score 0-1
    
    # Relationships
    node_executions = db.relationship('NodeExecution', backref='job', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<PropertyExtractionJob {self.id}: {self.url[:50]}...>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'url': self.url,
            'status': self.status.value,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'error_message': self.error_message,
            'extraction_duration': self.extraction_duration,
            'accuracy_score': self.accuracy_score,
            'basic_info_data': json.loads(self.basic_info_data) if self.basic_info_data else None,
            'description_data': json.loads(self.description_data) if self.description_data else None,
            'configuration_data': json.loads(self.configuration_data) if self.configuration_data else None,
            'tenancy_data': json.loads(self.tenancy_data) if self.tenancy_data else None,
            'merged_data': json.loads(self.merged_data) if self.merged_data else None,
            'node_executions': [node.to_dict() for node in self.node_executions]
        }
    
    def set_basic_info_data(self, data):
        """Set basic info data as JSON string"""
        self.basic_info_data = json.dumps(data) if data else None
    
    def set_description_data(self, data):
        """Set description data as JSON string"""
        self.description_data = json.dumps(data) if data else None
    
    def set_configuration_data(self, data):
        """Set configuration data as JSON string"""
        self.configuration_data = json.dumps(data) if data else None
    
    def set_tenancy_data(self, data):
        """Set tenancy data as JSON string"""
        self.tenancy_data = json.dumps(data) if data else None
    
    def set_merged_data(self, data):
        """Set merged data as JSON string"""
        self.merged_data = json.dumps(data) if data else None

class NodeExecution(db.Model):
    """Table for tracking individual node execution details"""
    __tablename__ = 'node_executions'
    
    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey('property_extraction_jobs.id'), nullable=False)
    node_name = db.Column(db.String(50), nullable=False)  # node1, node2, node3, node4
    status = db.Column(db.Enum(NodeStatus), default=NodeStatus.PENDING, nullable=False)
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    execution_duration = db.Column(db.Float)  # Duration in seconds
    
    # Execution details
    prompt_used = db.Column(db.Text)  # The prompt sent to GPT-4o
    raw_response = db.Column(db.Text)  # Raw response from GPT-4o
    extracted_data = db.Column(db.Text)  # Parsed JSON data
    error_message = db.Column(db.Text)
    retry_count = db.Column(db.Integer, default=0)
    
    # Quality metrics
    confidence_score = db.Column(db.Float)  # Confidence in extraction quality
    data_completeness = db.Column(db.Float)  # Percentage of expected fields extracted
    
    def __repr__(self):
        return f'<NodeExecution {self.id}: Job {self.job_id} - {self.node_name}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'job_id': self.job_id,
            'node_name': self.node_name,
            'status': self.status.value,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'execution_duration': self.execution_duration,
            'extracted_data': json.loads(self.extracted_data) if self.extracted_data else None,
            'error_message': self.error_message,
            'retry_count': self.retry_count,
            'confidence_score': self.confidence_score,
            'data_completeness': self.data_completeness
        }
    
    def set_extracted_data(self, data):
        """Set extracted data as JSON string"""
        self.extracted_data = json.dumps(data) if data else None

class CompetitorAnalysis(db.Model):
    """Table for storing competitor property analysis"""
    __tablename__ = 'competitor_analyses'
    
    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey('property_extraction_jobs.id'), nullable=False)
    competitor_url = db.Column(db.Text, nullable=False)
    competitor_name = db.Column(db.String(100))
    extracted_data = db.Column(db.Text)  # JSON string
    similarity_score = db.Column(db.Float)  # How similar to main property
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationship
    job = db.relationship('PropertyExtractionJob', backref='competitor_analyses')
    
    def __repr__(self):
        return f'<CompetitorAnalysis {self.id}: Job {self.job_id} - {self.competitor_name}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'job_id': self.job_id,
            'competitor_url': self.competitor_url,
            'competitor_name': self.competitor_name,
            'extracted_data': json.loads(self.extracted_data) if self.extracted_data else None,
            'similarity_score': self.similarity_score,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    def set_extracted_data(self, data):
        """Set extracted data as JSON string"""
        self.extracted_data = json.dumps(data) if data else None

class SystemConfiguration(db.Model):
    """Table for storing system configuration and settings"""
    __tablename__ = 'system_configurations'
    
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.Text, nullable=False)
    description = db.Column(db.Text)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<SystemConfiguration {self.key}: {self.value[:50]}...>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'key': self.key,
            'value': self.value,
            'description': self.description,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

