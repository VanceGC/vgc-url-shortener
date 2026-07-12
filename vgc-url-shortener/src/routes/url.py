from flask import Blueprint, request, jsonify, redirect, abort
from src.models.url import db, Url, Click, UrlEditHistory, UrlStats
from src.routes.auth import auth_required, optional_auth
from datetime import datetime, date
from sqlalchemy import func, desc
import requests
from urllib.parse import urlparse

url_bp = Blueprint('url', __name__)

# Utility functions
def get_client_ip():
    """Get client IP address from request"""
    if request.environ.get('HTTP_X_FORWARDED_FOR'):
        return request.environ['HTTP_X_FORWARDED_FOR'].split(',')[0].strip()
    return request.environ.get('REMOTE_ADDR', 'unknown')

def get_page_title(url):
    """Fetch page title from URL"""
    try:
        response = requests.get(url, timeout=5, headers={'User-Agent': 'VGC URL Shortener Bot'})
        if response.status_code == 200:
            content = response.text
            start = content.find('<title>')
            end = content.find('</title>')
            if start != -1 and end != -1:
                return content[start+7:end].strip()
    except:
        pass
    return None

# API Routes (Protected)
@url_bp.route('/shorten', methods=['POST'])
@auth_required
def shorten_url():
    """Create a new short URL with enhanced features"""
    try:
        data = request.get_json()
        
        if not data or 'url' not in data:
            return jsonify({'error': 'URL is required'}), 400
        
        original_url = data['url'].strip()
        custom_alias = data.get('custom_alias', '').strip()
        title = data.get('title', '').strip()
        description = data.get('description', '').strip()
        tags = data.get('tags', [])
        
        # Validate original URL
        if not Url.is_valid_url(original_url):
            return jsonify({'error': 'Invalid URL format'}), 400
        
        # Add protocol if missing
        if not original_url.startswith(('http://', 'https://')):
            original_url = 'https://' + original_url
        
        # Fetch page title if not provided
        if not title:
            title = get_page_title(original_url)
        
        # Handle custom alias
        if custom_alias:
            if not Url.is_valid_short_code(custom_alias):
                return jsonify({'error': 'Custom alias must be 3-10 alphanumeric characters'}), 400
            
            # Check if custom alias already exists
            if Url.query.filter_by(short_code=custom_alias).first():
                return jsonify({'error': 'Custom alias already exists'}), 409
            
            short_code = custom_alias
            is_custom = True
        else:
            short_code = Url.generate_short_code()
            is_custom = False
        
        # Create new URL record
        new_url = Url(
            short_code=short_code,
            original_url=original_url,
            title=title,
            description=description,
            custom_alias=is_custom,
            created_by_ip=get_client_ip(),
            tags=','.join(tags) if tags else None
        )
        
        db.session.add(new_url)
        db.session.commit()
        
        # Return the short URL
        short_url = f"https://vgc.to/{short_code}"
        
        return jsonify({
            'short_url': short_url,
            'short_code': short_code,
            'original_url': original_url,
            'title': title,
            'description': description,
            'tags': tags,
            'created_at': new_url.created_at.isoformat(),
            'auth_type': request.auth_info['type']
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Internal server error'}), 500

@url_bp.route('/info/<short_code>', methods=['GET'])
@auth_required
def get_url_info(short_code):
    """Get detailed information about a short URL"""
    url = Url.query.filter_by(short_code=short_code, is_active=True).first()
    
    if not url:
        return jsonify({'error': 'Short URL not found'}), 404
    
    return jsonify(url.to_dict(include_stats=True))

@url_bp.route('/edit/<short_code>', methods=['PUT'])
@auth_required
def edit_url(short_code):
    """Edit an existing short URL"""
    try:
        url = Url.query.filter_by(short_code=short_code, is_active=True).first()
        
        if not url:
            return jsonify({'error': 'Short URL not found'}), 404
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Store old values for history
        old_url = url.original_url
        old_title = url.title
        
        # Update fields
        new_url = data.get('url', url.original_url).strip()
        new_title = data.get('title', url.title)
        new_description = data.get('description', url.description)
        new_tags = data.get('tags', url.tags.split(',') if url.tags else [])
        edit_reason = data.get('reason', '').strip()
        
        # Validate new URL if changed
        if new_url != old_url:
            if not Url.is_valid_url(new_url):
                return jsonify({'error': 'Invalid URL format'}), 400
            
            # Add protocol if missing
            if not new_url.startswith(('http://', 'https://')):
                new_url = 'https://' + new_url
            
            # Fetch new title if not provided and URL changed
            if not new_title or new_title == old_title:
                fetched_title = get_page_title(new_url)
                if fetched_title:
                    new_title = fetched_title
        
        # Create edit history record
        edit_history = UrlEditHistory(
            url_id=url.id,
            old_url=old_url,
            new_url=new_url,
            old_title=old_title,
            new_title=new_title,
            edited_by_ip=get_client_ip(),
            edit_reason=edit_reason
        )
        
        # Update URL
        url.original_url = new_url
        url.title = new_title
        url.description = new_description
        url.tags = ','.join(new_tags) if new_tags else None
        url.updated_at = datetime.utcnow()
        
        db.session.add(edit_history)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'URL updated successfully',
            'url': url.to_dict()
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Internal server error'}), 500

@url_bp.route('/history/<short_code>', methods=['GET'])
@auth_required
def get_url_history(short_code):
    """Get edit history for a short URL"""
    url = Url.query.filter_by(short_code=short_code).first()
    
    if not url:
        return jsonify({'error': 'Short URL not found'}), 404
    
    history = UrlEditHistory.query.filter_by(url_id=url.id)\
                                 .order_by(desc(UrlEditHistory.edited_at))\
                                 .all()
    
    return jsonify({
        'url': url.to_dict(),
        'edit_history': [h.to_dict() for h in history]
    })

@url_bp.route('/urls', methods=['GET'])
@auth_required
def get_all_urls():
    """Get all URLs with enhanced filtering and pagination"""
    page = request.args.get('page', 1, type=int)
    limit = min(request.args.get('limit', 50, type=int), 100)
    search = request.args.get('search', '').strip()
    tag = request.args.get('tag', '').strip()
    sort_by = request.args.get('sort', 'created_at')  # created_at, clicks, updated_at
    order = request.args.get('order', 'desc')  # asc, desc
    
    query = Url.query.filter_by(is_active=True)
    
    # Apply search filter
    if search:
        query = query.filter(
            db.or_(
                Url.original_url.contains(search),
                Url.title.contains(search),
                Url.description.contains(search),
                Url.short_code.contains(search)
            )
        )
    
    # Apply tag filter
    if tag:
        query = query.filter(Url.tags.contains(tag))
    
    # Apply sorting
    if sort_by == 'clicks':
        sort_column = Url.clicks
    elif sort_by == 'updated_at':
        sort_column = Url.updated_at
    else:
        sort_column = Url.created_at
    
    if order == 'asc':
        query = query.order_by(sort_column.asc())
    else:
        query = query.order_by(sort_column.desc())
    
    urls = query.paginate(page=page, per_page=limit, error_out=False)
    
    return jsonify({
        'urls': [url.to_dict(include_stats=True) for url in urls.items],
        'total': urls.total,
        'page': page,
        'pages': urls.pages,
        'has_next': urls.has_next,
        'has_prev': urls.has_prev,
        'search': search,
        'tag': tag,
        'sort_by': sort_by,
        'order': order
    })

@url_bp.route('/delete/<short_code>', methods=['DELETE'])
@auth_required
def delete_url(short_code):
    """Soft delete a short URL"""
    url = Url.query.filter_by(short_code=short_code, is_active=True).first()
    
    if not url:
        return jsonify({'error': 'Short URL not found'}), 404
    
    # Soft delete
    url.is_active = False
    url.updated_at = datetime.utcnow()
    
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'URL deleted successfully'})

@url_bp.route('/restore/<short_code>', methods=['POST'])
@auth_required
def restore_url(short_code):
    """Restore a soft-deleted URL"""
    url = Url.query.filter_by(short_code=short_code, is_active=False).first()
    
    if not url:
        return jsonify({'error': 'Deleted URL not found'}), 404
    
    url.is_active = True
    url.updated_at = datetime.utcnow()
    
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'URL restored successfully'})

@url_bp.route('/stats/<short_code>', methods=['GET'])
@auth_required
def get_url_stats(short_code):
    """Get detailed statistics for a short URL"""
    url = Url.query.filter_by(short_code=short_code, is_active=True).first()
    
    if not url:
        return jsonify({'error': 'Short URL not found'}), 404
    
    # Get click statistics
    total_clicks = url.clicks
    
    # Get recent clicks (last 30)
    recent_clicks = Click.query.filter_by(url_id=url.id)\
                              .order_by(Click.clicked_at.desc())\
                              .limit(30).all()
    
    # Get daily stats for last 30 days
    daily_stats = db.session.query(
        func.date(Click.clicked_at).label('date'),
        func.count(Click.id).label('clicks'),
        func.count(func.distinct(Click.ip_address)).label('unique_clicks')
    ).filter(
        Click.url_id == url.id,
        Click.clicked_at >= datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    ).group_by(func.date(Click.clicked_at)).all()
    
    # Get top referrers
    top_referrers = db.session.query(
        Click.referer,
        func.count(Click.id).label('count')
    ).filter(
        Click.url_id == url.id,
        Click.referer.isnot(None)
    ).group_by(Click.referer).order_by(desc('count')).limit(10).all()
    
    return jsonify({
        'url_info': url.to_dict(),
        'total_clicks': total_clicks,
        'recent_clicks': [click.to_dict() for click in recent_clicks],
        # func.date() returns a str on SQLite and a date object on other backends
        'daily_stats': [{'date': stat.date if isinstance(stat.date, str) else stat.date.isoformat(), 'clicks': stat.clicks, 'unique_clicks': stat.unique_clicks} for stat in daily_stats],
        'top_referrers': [{'referer': ref.referer, 'count': ref.count} for ref in top_referrers]
    })

@url_bp.route('/search', methods=['GET'])
@auth_required
def search_urls():
    """Advanced search for URLs"""
    query_text = request.args.get('q', '').strip()
    
    if not query_text:
        return jsonify({'error': 'Search query required'}), 400
    
    # Search in multiple fields
    urls = Url.query.filter(
        Url.is_active == True,
        db.or_(
            Url.original_url.contains(query_text),
            Url.title.contains(query_text),
            Url.description.contains(query_text),
            Url.short_code.contains(query_text),
            Url.tags.contains(query_text)
        )
    ).order_by(desc(Url.clicks)).limit(20).all()
    
    return jsonify({
        'query': query_text,
        'results': [url.to_dict(include_stats=True) for url in urls],
        'count': len(urls)
    })

@url_bp.route('/tags', methods=['GET'])
@auth_required
def get_all_tags():
    """Get all unique tags"""
    urls_with_tags = Url.query.filter(
        Url.is_active == True,
        Url.tags.isnot(None)
    ).all()
    
    all_tags = set()
    for url in urls_with_tags:
        if url.tags:
            tags = [tag.strip() for tag in url.tags.split(',')]
            all_tags.update(tags)
    
    return jsonify({
        'tags': sorted(list(all_tags))
    })

@url_bp.route('/health', methods=['GET'])
@optional_auth
def health_check():
    """Health check endpoint (public but shows more info when authenticated)"""
    total_urls = Url.query.filter_by(is_active=True).count()
    total_clicks = db.session.query(func.sum(Url.clicks)).scalar() or 0
    
    response_data = {
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'version': '2.0'
    }
    
    # Show detailed stats only when authenticated
    if request.auth_info['authenticated']:
        response_data.update({
            'total_urls': total_urls,
            'total_clicks': total_clicks,
            'auth_type': request.auth_info['type']
        })
    
    return jsonify(response_data)

# Redirect route (for short URLs) - Public access
@url_bp.route('/<short_code>')
def redirect_url(short_code):
    """Redirect to the original URL and track the click"""
    # Skip API routes and static files
    if short_code.startswith('api') or '.' in short_code:
        abort(404)
    
    url = Url.query.filter_by(short_code=short_code, is_active=True).first()
    
    if not url:
        abort(404)
    
    # Check if URL has expired
    if url.is_expired():
        abort(410)  # Gone
    
    # Record the click
    click = Click(
        url_id=url.id,
        ip_address=get_client_ip(),
        user_agent=request.headers.get('User-Agent'),
        referer=request.headers.get('Referer')
    )
    
    # Increment click counter
    url.clicks += 1
    
    # Update daily stats
    today = date.today()
    daily_stat = UrlStats.query.filter_by(url_id=url.id, date=today).first()
    if daily_stat:
        daily_stat.clicks += 1
    else:
        daily_stat = UrlStats(url_id=url.id, date=today, clicks=1, unique_clicks=1)
        db.session.add(daily_stat)
    
    db.session.add(click)
    db.session.commit()
    
    return redirect(url.original_url, code=302)
