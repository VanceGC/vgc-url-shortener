from flask import Flask, request, jsonify, redirect, session, url_for, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from sqlalchemy import inspect, text
from sqlalchemy.exc import OperationalError
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

from og_metadata import fetch_open_graph, is_preview_crawler, validate_http_url

app = Flask(__name__)
CORS(app)

app.secret_key = os.environ.get('SECRET_KEY', 'change-this-in-production')
app.permanent_session_lifetime = timedelta(days=60)

# MySQL config
DB_USER = os.environ.get('DB_USER', 'vgcto')
DB_PASS = os.environ.get('DB_PASS', 'vgctopass')
DB_HOST = os.environ.get('DB_HOST', 'db')
DB_NAME = os.environ.get('DB_NAME', 'vgcto')

app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    'DATABASE_URL',
    f'mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}/{DB_NAME}'
)
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
    og_mode = db.Column(db.String(20), nullable=False, default='destination')
    og_title = db.Column(db.String(255), nullable=True)
    og_description = db.Column(db.String(1000), nullable=True)
    og_image = db.Column(db.String(2048), nullable=True)


def normalize_og_mode(value):
    return value if value in {'destination', 'custom'} else 'destination'


def clean_text(value, limit):
    return value.strip()[:limit] if isinstance(value, str) else ''


def clean_optional_url(value):
    value = clean_text(value, 2048)
    return validate_http_url(value) if value else ''


def refresh_destination_metadata(link):
    try:
        metadata = fetch_open_graph(link.original_url)
    except Exception as exc:
        app.logger.warning("Could not fetch Open Graph metadata for %s: %s", link.original_url, exc)
        metadata = {'title': '', 'description': '', 'image': ''}

    link.og_title = metadata['title'][:255] or None
    link.og_description = metadata['description'][:1000] or None
    link.og_image = metadata['image'][:2048] or None


def serialize_link(link):
    return {
        'id': link.id,
        'short': link.short,
        'original_url': link.original_url,
        'label': link.label or '',
        'click_count': link.click_count,
        'created_at': link.created_at.isoformat() if link.created_at else None,
        'last_clicked': link.last_clicked.isoformat() if link.last_clicked else None,
        'og_mode': link.og_mode or 'destination',
        'og_title': link.og_title or '',
        'og_description': link.og_description or '',
        'og_image': link.og_image or ''
    }

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
        if is_preview_crawler(request.headers.get('User-Agent')):
            if (entry.og_mode or 'destination') == 'destination' and not any([
                entry.og_title, entry.og_description, entry.og_image
            ]):
                refresh_destination_metadata(entry)
                db.session.commit()

            return render_template(
                'redirect.html',
                destination=entry.original_url,
                short_url=request.url,
                title=entry.og_title or entry.label or entry.original_url,
                description=entry.og_description or '',
                image=entry.og_image or ''
            )

        entry.click_count += 1
        entry.last_clicked = datetime.utcnow()
        db.session.commit()
        return redirect(entry.original_url)
    return "Short URL not found", 404

@app.route('/api/shorten', methods=['POST'])
@login_required
def shorten():
    data = request.get_json(silent=True) or {}
    original_url = data.get('url')
    custom_alias = data.get('custom_alias')
    label = data.get('label', '')
    og_mode = normalize_og_mode(data.get('og_mode'))

    if not original_url:
        return jsonify({'error': 'URL is required'}), 400

    try:
        original_url = validate_http_url(original_url)
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400

    if custom_alias:
        if URLMap.query.filter_by(short=custom_alias).first():
            return jsonify({'error': 'Alias already in use'}), 409
        short = custom_alias
    else:
        short = ''.join(random.choices(string.ascii_letters + string.digits, k=6))
        while URLMap.query.filter_by(short=short).first():
            short = ''.join(random.choices(string.ascii_letters + string.digits, k=6))

    new_entry = URLMap(
        original_url=original_url,
        short=short,
        label=label,
        og_mode=og_mode
    )
    if og_mode == 'custom':
        try:
            og_image = clean_optional_url(data.get('og_image'))
        except ValueError as exc:
            return jsonify({'error': f'Preview image: {exc}'}), 400
        new_entry.og_title = clean_text(data.get('og_title'), 255) or None
        new_entry.og_description = clean_text(data.get('og_description'), 1000) or None
        new_entry.og_image = og_image or None
    else:
        refresh_destination_metadata(new_entry)

    db.session.add(new_entry)
    db.session.commit()

    return jsonify({'short_url': f"https://vgc.to/{short}", 'short': short}), 201

@app.route('/api/links')
@login_required
def list_links():
    links = URLMap.query.order_by(URLMap.created_at.desc()).all()
    return jsonify([serialize_link(link) for link in links])

@app.route('/api/edit/<string:shortcode>', methods=['PUT'])
@login_required
def edit_link(shortcode):
    data = request.get_json(silent=True) or {}
    new_url = data.get('new_url')
    new_label = data.get('label')

    link = URLMap.query.filter_by(short=shortcode).first()
    if not link:
        return jsonify({'error': 'Shortcode not found'}), 404

    og_mode = normalize_og_mode(data.get('og_mode', link.og_mode))

    if new_url:
        try:
            link.original_url = validate_http_url(new_url)
        except ValueError as exc:
            return jsonify({'error': str(exc)}), 400
    if new_label is not None:
        link.label = new_label

    link.og_mode = og_mode
    if og_mode == 'custom':
        try:
            og_image = clean_optional_url(data.get('og_image'))
        except ValueError as exc:
            return jsonify({'error': f'Preview image: {exc}'}), 400
        link.og_title = clean_text(data.get('og_title'), 255) or None
        link.og_description = clean_text(data.get('og_description'), 1000) or None
        link.og_image = og_image or None
    else:
        refresh_destination_metadata(link)

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

def ensure_open_graph_columns():
    columns = {column['name'] for column in inspect(db.engine).get_columns('url_map')}
    additions = {
        'og_mode': "VARCHAR(20) NOT NULL DEFAULT 'destination'",
        'og_title': 'VARCHAR(255) NULL',
        'og_description': 'VARCHAR(1000) NULL',
        'og_image': 'VARCHAR(2048) NULL'
    }
    for name, definition in additions.items():
        if name not in columns:
            try:
                db.session.execute(text(f'ALTER TABLE url_map ADD COLUMN {name} {definition}'))
                db.session.commit()
            except OperationalError as exc:
                db.session.rollback()
                error_code = exc.orig.args[0] if getattr(exc.orig, 'args', None) else None
                if error_code != 1060:
                    raise


with app.app_context():
    db.create_all()
    ensure_open_graph_columns()

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=False)
