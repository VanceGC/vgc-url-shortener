from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import string
import random
import re
from urllib.parse import urlparse

db = SQLAlchemy()

class Url(db.Model):
    __tablename__ = 'urls'
    
    id = db.Column(db.Integer, primary_key=True)
    short_code = db.Column(db.String(10), unique=True, nullable=False, index=True)
    original_url = db.Column(db.Text, nullable=False)
    title = db.Column(db.String(200), nullable=True)  # Page title for better management
    description = db.Column(db.Text, nullable=True)   # Optional description
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    clicks = db.Column(db.Integer, default=0)
    custom_alias = db.Column(db.Boolean, default=False)
    expires_at = db.Column(db.DateTime, nullable=True)
    is_active = db.Column(db.Boolean, default=True)   # For soft deletion
    created_by_ip = db.Column(db.String(45), nullable=True)  # Track creator IP
    tags = db.Column(db.String(500), nullable=True)   # Comma-separated tags for organization
    
    # Relationship to clicks and edit history
    click_records = db.relationship('Click', backref='url', lazy=True, cascade='all, delete-orphan')
    edit_history = db.relationship('UrlEditHistory', backref='url', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Url {self.short_code}: {self.original_url}>'

    def to_dict(self, include_stats=False):
        data = {
            'id': self.id,
            'short_code': self.short_code,
            'original_url': self.original_url,
            'title': self.title,
            'description': self.description,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'clicks': self.clicks,
            'custom_alias': self.custom_alias,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'is_active': self.is_active,
            'tags': self.tags.split(',') if self.tags else []
        }
        
        if include_stats:
            # Add recent click statistics
            recent_clicks = Click.query.filter_by(url_id=self.id)\
                                    .filter(Click.clicked_at >= datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0))\
                                    .count()
            data['clicks_today'] = recent_clicks
            
            # Add last click time
            last_click = Click.query.filter_by(url_id=self.id)\
                                  .order_by(Click.clicked_at.desc())\
                                  .first()
            data['last_clicked'] = last_click.clicked_at.isoformat() if last_click else None
        
        return data

    @staticmethod
    def generate_short_code(length=6):
        """Generate a random short code"""
        characters = string.ascii_letters + string.digits
        while True:
            code = ''.join(random.choice(characters) for _ in range(length))
            # Check if code already exists
            if not Url.query.filter_by(short_code=code).first():
                return code

    def is_expired(self):
        """Check if URL has expired"""
        if self.expires_at:
            return datetime.utcnow() > self.expires_at
        return False

    @staticmethod
    def is_valid_url(url):
        """Validate if the provided string is a valid URL"""
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except:
            return False

    @staticmethod
    def is_valid_short_code(code):
        """Validate short code format (alphanumeric, 3-10 chars)"""
        return bool(re.match(r'^[a-zA-Z0-9]{3,10}$', code))

class Click(db.Model):
    __tablename__ = 'clicks'
    
    id = db.Column(db.Integer, primary_key=True)
    url_id = db.Column(db.Integer, db.ForeignKey('urls.id'), nullable=False)
    clicked_at = db.Column(db.DateTime, default=datetime.utcnow)
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.Text)
    referer = db.Column(db.Text)
    country = db.Column(db.String(2), nullable=True)  # Country code
    city = db.Column(db.String(100), nullable=True)   # City name

    def __repr__(self):
        return f'<Click {self.id} for URL {self.url_id}>'

    def to_dict(self):
        return {
            'id': self.id,
            'url_id': self.url_id,
            'clicked_at': self.clicked_at.isoformat() if self.clicked_at else None,
            'ip_address': self.ip_address,
            'user_agent': self.user_agent,
            'referer': self.referer,
            'country': self.country,
            'city': self.city
        }

class UrlEditHistory(db.Model):
    __tablename__ = 'url_edit_history'
    
    id = db.Column(db.Integer, primary_key=True)
    url_id = db.Column(db.Integer, db.ForeignKey('urls.id'), nullable=False)
    old_url = db.Column(db.Text, nullable=False)
    new_url = db.Column(db.Text, nullable=False)
    old_title = db.Column(db.String(200), nullable=True)
    new_title = db.Column(db.String(200), nullable=True)
    edited_at = db.Column(db.DateTime, default=datetime.utcnow)
    edited_by_ip = db.Column(db.String(45), nullable=True)
    edit_reason = db.Column(db.Text, nullable=True)

    def __repr__(self):
        return f'<UrlEditHistory {self.id} for URL {self.url_id}>'

    def to_dict(self):
        return {
            'id': self.id,
            'url_id': self.url_id,
            'old_url': self.old_url,
            'new_url': self.new_url,
            'old_title': self.old_title,
            'new_title': self.new_title,
            'edited_at': self.edited_at.isoformat() if self.edited_at else None,
            'edit_reason': self.edit_reason
        }

class UrlStats(db.Model):
    __tablename__ = 'url_stats'
    
    id = db.Column(db.Integer, primary_key=True)
    url_id = db.Column(db.Integer, db.ForeignKey('urls.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    clicks = db.Column(db.Integer, default=0)
    unique_clicks = db.Column(db.Integer, default=0)  # Unique IP addresses
    
    # Composite index for efficient queries
    __table_args__ = (db.Index('idx_url_date', 'url_id', 'date'),)

    def __repr__(self):
        return f'<UrlStats {self.url_id} on {self.date}>'

    def to_dict(self):
        return {
            'id': self.id,
            'url_id': self.url_id,
            'date': self.date.isoformat() if self.date else None,
            'clicks': self.clicks,
            'unique_clicks': self.unique_clicks
        }

