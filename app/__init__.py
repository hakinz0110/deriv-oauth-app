from flask import Flask, send_from_directory
from app.config import Config
import os
import logging
from logging.handlers import RotatingFileHandler

def create_app():
    # Set template folder to project root/templates
    template_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'templates'))
    
    # Set static folder to project root/static for serving JS/CSS
    static_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static'))
    
    app = Flask(__name__, template_folder=template_dir, static_folder=static_dir, static_url_path='/static')
    app.config.from_object(Config)
    
    # ==================== PRODUCTION LOGGING ====================
    # Configure logging for production monitoring
    if not app.debug:
        # Set log level from environment (default: INFO)
        log_level = os.environ.get('LOG_LEVEL', 'INFO').upper()
        app.logger.setLevel(getattr(logging, log_level))
        
        # Create logs directory if it doesn't exist
        logs_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'logs'))
        if not os.path.exists(logs_dir):
            os.mkdir(logs_dir)
        
        # File handler with rotation (10MB per file, keep 10 files)
        file_handler = RotatingFileHandler(
            os.path.join(logs_dir, 'hts_trade.log'),
            maxBytes=10485760,  # 10MB
            backupCount=10
        )
        
        # Format: timestamp - level - module - message
        formatter = logging.Formatter(
            '[%(asctime)s] %(levelname)s in %(module)s: %(message)s'
        )
        file_handler.setFormatter(formatter)
        file_handler.setLevel(logging.INFO)
        
        app.logger.addHandler(file_handler)
        app.logger.info('HTS Trade startup - Production mode')
    
    # ==================== END PRODUCTION LOGGING ====================
    
    # ==================== SECURITY ENHANCEMENTS ====================
    
    # Initialize rate limiter (Flask-Limiter)
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address
    
    limiter = Limiter(
        app=app,
        key_func=get_remote_address,
        default_limits=["100 per minute"],  # Global default
        storage_uri="memory://",  # In-memory storage (sufficient for 100-1000 users)
        strategy="fixed-window"
    )
    
    # Make limiter available to routes
    app.limiter = limiter
    
    # Initialize caching (Flask-Caching)
    from flask_caching import Cache
    
    cache = Cache(app, config={
        'CACHE_TYPE': 'SimpleCache',  # In-memory LRU cache
        'CACHE_DEFAULT_TIMEOUT': 300,  # 5 minutes default
        'CACHE_THRESHOLD': 1000  # Max 1000 cached items
    })
    
    # Make cache available to routes
    app.cache = cache
    
    # ==================== END SECURITY ENHANCEMENTS ====================
    
    # Serve images from /img folder
    @app.route('/img/<path:filename>')
    def serve_image(filename):
        img_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'img'))
        return send_from_directory(img_dir, filename)
    
    # Register error handlers
    from app.errors import register_error_handlers
    register_error_handlers(app)
    
    # Register blueprints
    from app.routes import auth_bp
    app.register_blueprint(auth_bp)
    
    return app
