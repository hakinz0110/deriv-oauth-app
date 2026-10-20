from flask import Flask, send_from_directory
from app.config import Config
import os

def create_app():
    # Set template folder to project root/templates
    template_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'templates'))
    
    # Set static folder to project root/static for serving JS/CSS
    static_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static'))
    
    app = Flask(__name__, template_folder=template_dir, static_folder=static_dir, static_url_path='/static')
    app.config.from_object(Config)
    
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
