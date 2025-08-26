import os
import sys
from flask import Flask, send_from_directory, jsonify, request
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

    # Minimal request logging for diagnostics
    @app.before_request
    def _log_request_start():
        try:
            get_logger().info(f"REQ {request.method} {request.path}")
        except Exception:
            pass

    @app.after_request
    def _log_request_end(response):
        try:
            get_logger().info(f"RES {response.status_code} {response.content_type}")
        except Exception:
            pass
        return response

    @app.route('/api/health', methods=['GET'])
    def health_check():
        """Lightweight health endpoint; always 200 with diagnostics."""
        cfg = get_config()
        validation = cfg.validate_config()
        diagnostics = {
            'status': 'healthy' if validation.get('valid') else 'unhealthy',
            'configuration': {
                'issues': validation.get('issues', []),
                'api': {
                    'has_openai_key': validation.get('config_summary', {}).get('api', {}).get('has_openai_key', False),
                    'openai_model': validation.get('config_summary', {}).get('api', {}).get('openai_model')
                },
                'app': validation.get('config_summary', {}).get('app', {})
            },
            'version': '1.0.0'
        }
        return jsonify(diagnostics), 200

    # No catch-all route needed for API-only backend

    return app

if __name__ == '__main__':
    app = create_app()
    logger = get_logger()
    logger.info("Property Onboarding Tool with In-Memory Storage startup")
    
    config = get_config()
    app.run(host=config.app.host, port=config.app.port, debug=config.app.debug)

