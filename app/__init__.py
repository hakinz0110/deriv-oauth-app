from flask import Flask
from app.config import Config
import os

def create_app():
    # Set template folder to project root/templates
    template_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'templates'))
    
    # Set static folder to project root/img for serving images
    static_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'img'))
    
    app = Flask(__name__, template_folder=template_dir, static_folder=static_dir, static_url_path='/img')
    app.config.from_object(Config)
    
    # Register error handlers
    from app.errors import register_error_handlers
    register_error_handlers(app)
    
    # Register blueprints
    from app.routes import auth_bp
    app.register_blueprint(auth_bp)
    
    return app
