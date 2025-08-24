import os
import sys

# Add the parent directory of src to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'src')))

from src.main import create_app
from src.utils.config import get_config
from src.utils.logging_config import get_logger

app = create_app()

if __name__ == '__main__':
    logger = get_logger()
    logger.info("Property Onboarding Tool with Orchestration System startup")
    
    config = get_config()
    app.run(host=config.app.host, port=config.app.port, debug=config.app.debug)

