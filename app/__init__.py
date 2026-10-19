from flask import Flask
from app.config import Config

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    
    # Register error handlers
    from app.errors import register_error_handlers
    register_error_handlers(app)
    
    # Register blueprints
    from app.routes import auth_bp
    app.register_blueprint(auth_bp)
    
    return app
