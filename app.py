"""
Postman Collection to Pytest Migrator
Main Application Entry Point (Flask Server)
"""

import os
from flask import Flask, render_template
from dotenv import load_dotenv

# Load environment configuration variables
load_dotenv()

def create_app():
    app = Flask(__name__, 
                static_folder="static", 
                template_folder="templates")
    
    # Configure application secrets and upload configurations
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "pytest_migrator_secure_session_key")
    app.config["UPLOAD_FOLDER"] = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
    app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50MB File Size Limit (Security Constraint)
    
    # Ensure temporary upload folder exists
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    
    # Initialize the database
    from database.db import init_db
    init_db()
    
    # Register Routing Blueprints
    from routes.routes import main_blueprint
    app.register_blueprint(main_blueprint)
    
    return app

app = create_app()

if __name__ == "__main__":
    port = 3000
    debug_mode = os.getenv("FLASK_ENV") == "development"
    
    print(f"Starting Pytest Migrator Flask server on port {port}...")
    app.run(host="0.0.0.0", port=port, debug=debug_mode)
