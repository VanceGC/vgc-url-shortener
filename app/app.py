from flask import Flask, request, jsonify, redirect, session, url_for, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from functools import wraps
from datetime import timedelta, datetime
import os
import string
import random
import hashlib
import qrcode
import qrcode.image.svg
import io
import base64

app = Flask(__name__)
CORS(app)

app.secret_key = os.environ.get('SECRET_KEY', 'change-this-in-production')
app.permanent_session_lifetime = timedelta(days=60)

# MySQL config
DB_USER = os.environ.get('DB_USER', 'vgcto')
DB_PASS = os.environ.get('DB_PASS', 'vgctopass')
DB_HOST = os.environ.get('DB_HOST', 'db')
DB_NAME = os.environ.get('DB_NAME', 'vgcto')

app.config['SQLALCHEMY_DATABASE_URI'] = f'mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}/{DB_NAME}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'admin')
ADMIN_PASSWORD_HASH = os.environ.get('ADMIN_PASSWORD_HASH', '')

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

class URLMap(db.Model):
    __tablename__ = 'url_map'
    id = db.Column(db.Integer, primary_key=True)
    original_url = db.Column(db.String(2048), nullable=False)
    short = db.Column(db.String(50), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    click_count = db.Column(db.Integer, default=0)
    last_clicked = db.Column(db.DateTime, nullable=True)
    label = db.Column(db.String(255), nullable=True)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def serve_index():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        data = request.form or request.get_json()
        username = data.get('username')
        password = data.get('password')
        password_hash = hash_password(password) if password else ''
        if username == ADMIN_USERNAME and password_hash == ADMIN_PASSWORD_HASH:
            session['logged_in'] = True
            session.permanent = True
            return redirect(url_for('serve_index'))
        error = "Invalid credentials"
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/<string:shortcode>')
def redirect_short_url(shortcode):
    # Skip static/special routes
    if shortcode in ['login', 'logout', 'admin', 'api', 'static']:
        return "Not found", 404
    entry = URLMap.query.filter_by(short=shortcode).first()
    if entry:
        entry.click_count += 1
        entry.last_clicked = datetime.utcnow()
        db.session.commit()
        return redirect(entry.original_url)
    return "Short URL not found", 404

@app.route('/api/shorten', methods=['POST'])
@login_required
def shorten():
    data = request.get_json()
    original_url = data.get('url')
    custom_alias = data.get('custom_alias')
    label = data.get('label', '')

    if not original_url:
        return jsonify({'error': 'URL is required'}), 400

    if custom_alias:
        if URLMap.query.filter_by(short=custom_alias).first():
            return jsonify({'error': 'Alias already in use'}), 409
        short = custom_alias
    else:
        short = ''.join(random.choices(string.ascii_letters + string.digits, k=6))
        while URLMap.query.filter_by(short=short).first():
            short = ''.join(random.choices(string.ascii_letters + string.digits, k=6))

    new_entry = URLMap(original_url=original_url, short=short, label=label)
    db.session.add(new_entry)
    db.session.commit()

    return jsonify({'short_url': f"https://vgc.to/{short}", 'short': short}), 201

@app.route('/api/links')
@login_required
def list_links():
    links = URLMap.query.order_by(URLMap.created_at.desc()).all()
    return jsonify([
        {
            'id': link.id,
            'short': link.short,
            'original_url': link.original_url,
            'label': link.label or '',
            'click_count': link.click_count,
            'created_at': link.created_at.isoformat() if link.created_at else None,
            'last_clicked': link.last_clicked.isoformat() if link.last_clicked else None
        }
        for link in links
    ])

@app.route('/api/edit/<string:shortcode>', methods=['PUT'])
@login_required
def edit_link(shortcode):
    data = request.get_json()
    new_url = data.get('new_url')
    new_label = data.get('label')

    link = URLMap.query.filter_by(short=shortcode).first()
    if not link:
        return jsonify({'error': 'Shortcode not found'}), 404

    if new_url:
        link.original_url = new_url
    if new_label is not None:
        link.label = new_label
    db.session.commit()

    return jsonify({'message': 'Link updated successfully'})

@app.route('/api/delete/<string:shortcode>', methods=['DELETE'])
@login_required
def delete_link(shortcode):
    link = URLMap.query.filter_by(short=shortcode).first()
    if not link:
        return jsonify({'error': 'Shortcode not found'}), 404
    db.session.delete(link)
    db.session.commit()
    return jsonify({'message': 'Link deleted successfully'})

@app.route('/api/qr/<string:shortcode>')
@login_required
def get_qr(shortcode):
    link = URLMap.query.filter_by(short=shortcode).first()
    if not link:
        return jsonify({'error': 'Shortcode not found'}), 404

    short_url = f"https://vgc.to/{shortcode}"
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(short_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    img_base64 = base64.b64encode(buffer.getvalue()).decode()

    return jsonify({'qr': f"data:image/png;base64,{img_base64}", 'url': short_url})

@app.route('/api/stats')
@login_required
def get_stats():
    total_links = URLMap.query.count()
    total_clicks = db.session.query(db.func.sum(URLMap.click_count)).scalar() or 0
    top_links = URLMap.query.order_by(URLMap.click_count.desc()).limit(5).all()
    return jsonify({
        'total_links': total_links,
        'total_clicks': total_clicks,
        'top_links': [
            {'short': l.short, 'label': l.label or l.short, 'clicks': l.click_count}
            for l in top_links
        ]
    })

with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=False)
