from flask import Blueprint, request, jsonify, session
from functools import wraps
import hashlib
import secrets
import os
from datetime import datetime, timedelta

auth_bp = Blueprint('auth', __name__)

# Authentication configuration
AUTH_PASSWORD = "B33fst3\/\/"
SESSION_TIMEOUT = 24 * 60 * 60  # 24 hours in seconds

# Generate a persistent API key (in production, store this securely)
API_KEY = os.environ.get('VGC_API_KEY', 'vgc_' + secrets.token_urlsafe(32))

def hash_password(password):
    """Hash password for secure comparison"""
    return hashlib.sha256(password.encode()).hexdigest()

def check_password(password):
    """Check if provided password matches the configured password"""
    return hash_password(password) == hash_password(AUTH_PASSWORD)

def check_api_key(api_key):
    """Check if provided API key is valid"""
    return api_key == API_KEY

def get_auth_from_request():
    """Extract authentication from request (session or API key)"""
    # Check for API key in headers
    api_key = request.headers.get('X-API-Key') or request.headers.get('Authorization', '').replace('Bearer ', '')
    if api_key and check_api_key(api_key):
        return {'type': 'api_key', 'authenticated': True}
    
    # Check for session authentication
    if session.get('authenticated'):
        return {'type': 'session', 'authenticated': True}
    
    return {'type': None, 'authenticated': False}

def auth_required(f):
    """Decorator to require authentication (session or API key) for API endpoints"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_info = get_auth_from_request()
        if not auth_info['authenticated']:
            return jsonify({
                'error': 'Authentication required', 
                'code': 'AUTH_REQUIRED',
                'message': 'Please provide a valid API key in X-API-Key header or log in via web interface'
            }), 401
        
        # Add auth info to request context
        request.auth_info = auth_info
        return f(*args, **kwargs)
    return decorated_function

def optional_auth(f):
    """Decorator for endpoints that work with or without authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_info = get_auth_from_request()
        request.auth_info = auth_info
        return f(*args, **kwargs)
    return decorated_function

@auth_bp.route('/login', methods=['POST'])
def login():
    """Authenticate user with password"""
    try:
        data = request.get_json()
        
        if not data or 'password' not in data:
            return jsonify({'error': 'Password is required'}), 400
        
        password = data['password']
        
        if check_password(password):
            session['authenticated'] = True
            session['login_time'] = datetime.utcnow().isoformat()
            session.permanent = True
            
            return jsonify({
                'success': True,
                'message': 'Authentication successful',
                'session_timeout': SESSION_TIMEOUT,
                'api_key': API_KEY,
                'api_key_info': {
                    'description': 'Use this API key for programmatic access',
                    'header_name': 'X-API-Key',
                    'example': f'curl -H "X-API-Key: {API_KEY}" https://vgc.to/api/health'
                }
            })
        else:
            return jsonify({'error': 'Invalid password'}), 401
            
    except Exception as e:
        return jsonify({'error': 'Authentication failed'}), 500

@auth_bp.route('/logout', methods=['POST'])
def logout():
    """Log out user and clear session"""
    session.clear()
    return jsonify({'success': True, 'message': 'Logged out successfully'})

@auth_bp.route('/status', methods=['GET'])
def auth_status():
    """Check authentication status"""
    auth_info = get_auth_from_request()
    
    response_data = {
        'authenticated': auth_info['authenticated'],
        'auth_type': auth_info['type'],
        'session_timeout': SESSION_TIMEOUT
    }
    
    if auth_info['authenticated'] and auth_info['type'] == 'session':
        response_data['login_time'] = session.get('login_time')
        response_data['api_key'] = API_KEY
        response_data['api_key_info'] = {
            'description': 'Use this API key for programmatic access (N8N, scripts, etc.)',
            'header_name': 'X-API-Key',
            'alternative_header': 'Authorization: Bearer {api_key}',
            'example_curl': f'curl -H "X-API-Key: {API_KEY}" https://vgc.to/api/shorten',
            'example_n8n': {
                'method': 'POST',
                'url': 'https://vgc.to/api/shorten',
                'headers': {
                    'Content-Type': 'application/json',
                    'X-API-Key': API_KEY
                },
                'body': {
                    'url': 'https://example.com',
                    'title': 'Example Link'
                }
            }
        }
    
    return jsonify(response_data)

@auth_bp.route('/verify', methods=['GET'])
@auth_required
def verify_auth():
    """Verify authentication (protected endpoint for testing)"""
    auth_info = request.auth_info
    
    return jsonify({
        'success': True,
        'message': 'Authentication verified',
        'auth_type': auth_info['type'],
        'login_time': session.get('login_time') if auth_info['type'] == 'session' else None,
        'timestamp': datetime.utcnow().isoformat()
    })

@auth_bp.route('/api-key', methods=['GET'])
@auth_required
def get_api_key():
    """Get API key information (requires authentication)"""
    return jsonify({
        'api_key': API_KEY,
        'description': 'Use this API key for programmatic access',
        'usage_examples': {
            'curl': f'curl -H "X-API-Key: {API_KEY}" https://vgc.to/api/shorten -d \'{{"url": "https://example.com"}}\'',
            'python': f'''
import requests

headers = {{"X-API-Key": "{API_KEY}", "Content-Type": "application/json"}}
data = {{"url": "https://example.com", "title": "My Link"}}
response = requests.post("https://vgc.to/api/shorten", json=data, headers=headers)
''',
            'n8n_headers': {
                'X-API-Key': API_KEY,
                'Content-Type': 'application/json'
            }
        },
        'supported_headers': [
            'X-API-Key: {api_key}',
            'Authorization: Bearer {api_key}'
        ]
    })

@auth_bp.route('/regenerate-api-key', methods=['POST'])
@auth_required
def regenerate_api_key():
    """Regenerate API key (requires authentication)"""
    global API_KEY
    API_KEY = 'vgc_' + secrets.token_urlsafe(32)
    
    return jsonify({
        'success': True,
        'message': 'API key regenerated successfully',
        'new_api_key': API_KEY,
        'warning': 'Update all applications using the old API key'
    })

