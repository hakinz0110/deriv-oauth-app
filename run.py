from app import create_app
import os

app = create_app()

if __name__ == '__main__':
    # Get port from environment variable or default to 5000
    port = int(os.environ.get('PORT', 5000))
    # Run with HTTPS in production
    # For development with self-signed cert: ssl_context='adhoc'
    app.run(host='0.0.0.0', port=port, debug=False)
