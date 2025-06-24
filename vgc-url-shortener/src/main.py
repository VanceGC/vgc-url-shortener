import os
import sys
# DON'T CHANGE THIS !!!
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from flask import Flask, send_from_directory, session
from flask_cors import CORS
from src.models.user import db
from src.models.url import Url, Click, UrlEditHistory, UrlStats
from src.routes.user import user_bp
from src.routes.url import url_bp
from src.routes.auth import auth_bp
from datetime import timedelta
import secrets

app = Flask(__name__, static_folder=os.path.join(os.path.dirname(__file__), 'static'))

# Enhanced configuration with session management
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'vgc-url-shortener-production-key-change-this')

# Session configuration for authentication
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)
app.config['SESSION_COOKIE_SECURE'] = False  # Set to True in production with HTTPS
app.config['SESSION_COOKIE_HTTPONLY'] = True  # Prevent JavaScript access
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# Enhanced CORS configuration
CORS(app, 
     origins=['https://vgc.to', 'https://www.vgc.to', 'http://localhost:3000', 'http://localhost:5000'],
     supports_credentials=True,
     allow_headers=['Content-Type', 'Authorization', 'X-API-Key'])

# Register blueprints
app.register_blueprint(user_bp, url_prefix='/api/users')
app.register_blueprint(auth_bp, url_prefix='/api/auth')
app.register_blueprint(url_bp, url_prefix='/api')

# Register redirect route at root level
@app.route('/<short_code>')
def redirect_short_url(short_code):
    """Handle short URL redirects at root level"""
    from src.routes.url import redirect_url
    return redirect_url(short_code)

# Database configuration
database_dir = os.path.join(os.path.dirname(__file__), 'database')
os.makedirs(database_dir, exist_ok=True)
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(database_dir, 'app.db')}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

with app.app_context():
    db.create_all()

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    """Serve frontend files"""
    static_folder_path = app.static_folder
    if static_folder_path is None:
        return "Static folder not configured", 404

    # Handle API routes first
    if path.startswith('api/'):
        return {"error": "API endpoint not found"}, 404

    # Handle short codes at root level (single alphanumeric string)
    if path and '/' not in path and '.' not in path and path.isalnum() and len(path) >= 3:
        return redirect_short_url(path)

    # Serve static files
    if path != "" and os.path.exists(os.path.join(static_folder_path, path)):
        return send_from_directory(static_folder_path, path)
    else:
        # Fallback to index.html for SPA routing
        index_path = os.path.join(static_folder_path, 'index.html')
        if os.path.exists(index_path):
            return send_from_directory(static_folder_path, 'index.html')
        else:
            return "index.html not found", 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

