import os
import sys
from flask import Flask, send_from_directory, jsonify
from flask_cors import CORS
from sqlalchemy import text

# Add the parent directory of src to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir)))

from src.models.user import db
from src.routes.user import user_bp
from src.routes.property import property_bp
from src.utils.config import get_config
from src.utils.logging_config import setup_flask_logging, get_logger
from src.orchestration.job_queue import initialize_job_queue
import asyncio
import threading

def create_app():
    """Configure the Flask application"""
    app = Flask(__name__, static_folder=os.path.join(os.path.dirname(__file__), 'static'))

    # Load configuration
    config = get_config()
    app.config['SECRET_KEY'] = config.app.secret_key
    app.config['SQLALCHEMY_DATABASE_URI'] = config.database.database_uri
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = config.database.track_modifications

    # Enable CORS for all routes
    CORS(app, origins=config.app.cors_origins)

    # Register blueprints
    app.register_blueprint(user_bp, url_prefix='/api')
    app.register_blueprint(property_bp, url_prefix='/api')

    # Initialize database
    db.init_app(app)
    with app.app_context():
        db.create_all()

    # Setup logging
    setup_flask_logging(app)

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
        try:
            # Test database connection
            db.session.execute(text('SELECT 1'))
            db_status = 'healthy'
        except Exception as e:
            db_status = f'unhealthy: {str(e)}'
        
        # Validate configuration
        config_validation = get_config().validate_config()
        
        # Check job queue status
        try:
            from src.orchestration.job_queue import get_job_queue
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
        
        return jsonify({
            'status': 'healthy' if db_status == 'healthy' and config_validation['valid'] else 'unhealthy',
            'database': db_status,
            'configuration': config_validation,
            'job_queue': queue_status,
            'version': '1.0.0'
        })

    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def serve(path):
        static_folder_path = app.static_folder
        if static_folder_path is None:
                return "Static folder not configured", 404

        if path != "" and os.path.exists(os.path.join(static_folder_path, path)):
            return send_from_directory(static_folder_path, path)
        else:
            index_path = os.path.join(static_folder_path, 'index.html')
            if os.path.exists(index_path):
                return send_from_directory(static_folder_path, 'index.html')
            else:
                return "index.html not found", 404

    return app

if __name__ == '__main__':
    app = create_app()
    logger = get_logger()
    logger.info("Property Onboarding Tool with Orchestration System startup")
    
    config = get_config()
    app.run(host=config.app.host, port=config.app.port, debug=config.app.debug)


