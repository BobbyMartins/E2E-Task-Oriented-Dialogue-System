#!/usr/bin/env python3
"""
TOD User Simulator - Entry point for running the application
"""

import os
import sys

# Add src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from app import app

if __name__ == '__main__':
    # Set debug mode based on environment
    debug_mode = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    
    # Set host and port
    host = os.getenv('FLASK_HOST', '127.0.0.1')
    port = int(os.getenv('FLASK_PORT', 5000))
    
    print(f"Starting TOD User Simulator on {host}:{port}")
    print(f"Debug mode: {debug_mode}")
    print(f"Access the application at: http://{host}:{port}")
    print(f"TOD Simulator at: http://{host}:{port}/tod_simulator")
    
    app.run(host=host, port=port, debug=debug_mode)