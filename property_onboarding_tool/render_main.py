#!/usr/bin/env python3
"""
Production entry point for Render deployment
"""

import os
from src.main_memory import create_app

app = create_app()

if __name__ == "__main__":
    # Get port from environment variable (Render sets this)
    port = int(os.environ.get("PORT", 10000))
    
    # Run the app
    app.run(
        host="0.0.0.0",
        port=port,
        debug=False
    )
