import os
import sys
from flask import Flask, send_from_directory, jsonify
from flask_cors import CORS

# Add the parent directory of src to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir)))

from src.routes.property_memory import property_bp
from src.utils.config import get_config
from src.utils.logging_config import setup_flask_logging, get_logger
from src.orchestration.job_queue_memory import initialize_job_queue
from src.storage.memory_store import get_memory_store
import asyncio
import threading

def create_app():
    """Configure the Flask application with in-memory storage"""
    app = Flask(__name__, static_folder=os.path.join(os.path.dirname(__file__), 'static'))

    # Load configuration
    config = get_config()
    app.config['SECRET_KEY'] = config.app.secret_key

    # Enable CORS for all routes
    CORS(app, origins=config.app.cors_origins)

    # Register blueprints
    app.register_blueprint(property_bp, url_prefix='/api')

    # Setup logging
    setup_flask_logging(app)

    # Initialize memory store
    memory_store = get_memory_store()

    # Initialize job queue in background thread
    def init_queue():
        """Initialize the job queue in a separate thread"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(initialize_job_queue())
            get_logger().info("Job queue initialized successfully")
            loop.run_forever()
        except Exception as e:
            get_logger().error(f"Failed to initialize job queue: {str(e)}")
        finally:
            loop.close()

    # Start job queue in background
    queue_thread = threading.Thread(target=init_queue, daemon=True)
    queue_thread.start()

    @app.route('/api/health', methods=['GET'])
    def health_check():
        """Health check endpoint with orchestration system status"""
        # Validate configuration
        config_validation = get_config().validate_config()
        
        # Check job queue status
        try:
            from src.orchestration.job_queue_memory import get_job_queue
            job_queue = get_job_queue()
            
            # Use asyncio to get queue stats
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                stats = loop.run_until_complete(job_queue.get_queue_stats())
                queue_status = {
                    'status': 'healthy',
                    'active_workers': stats.active_workers,
                    'queue_length': stats.queue_length,
                    'running_jobs': stats.running_jobs
                }
            finally:
                loop.close()
        except Exception as e:
            queue_status = {
                'status': 'unhealthy',
                'error': str(e)
            }
        
        # Check memory store
        try:
            memory_store = get_memory_store()
            store_stats = memory_store.get_queue_stats()
            memory_status = {
                'status': 'healthy',
                'total_jobs': store_stats.total_jobs,
                'running_jobs': store_stats.running_jobs,
                'completed_jobs': store_stats.completed_jobs,
                'failed_jobs': store_stats.failed_jobs
            }
        except Exception as e:
            memory_status = {
                'status': 'unhealthy',
                'error': str(e)
            }
        
        return jsonify({
            'status': 'healthy' if config_validation['valid'] else 'unhealthy',
            'storage': 'in-memory',
            'configuration': config_validation,
            'job_queue': queue_status,
            'memory_store': memory_status,
            'version': '1.0.0'
        })

    # No catch-all route needed for API-only backend

    return app

if __name__ == '__main__':
    app = create_app()
    logger = get_logger()
    logger.info("Property Onboarding Tool with In-Memory Storage startup")
    
    config = get_config()
    app.run(host=config.app.host, port=config.app.port, debug=config.app.debug)

