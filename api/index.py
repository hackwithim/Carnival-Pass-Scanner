import sys
import os

# Add root project directory to sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from app import app

class VercelPathFixMiddleware:
    """
    Vercel rewrites backend requests using the destination path (/api/index.py).
    This middleware restores the original request path from Vercel proxy headers
    (HTTP_X_NOW_PATHNAME, HTTP_X_FORWARDED_URI, HTTP_X_ORIGINAL_URI, HTTP_X_MATCHED_PATH, REQUEST_URI)
    so Flask routes all endpoints (/, /api/login, /api/scan, /static/...) accurately.
    """
    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        original_path = (
            environ.get('HTTP_X_NOW_PATHNAME') or
            environ.get('HTTP_X_FORWARDED_URI') or
            environ.get('HTTP_X_ORIGINAL_URI') or
            environ.get('HTTP_X_MATCHED_PATH') or
            environ.get('REQUEST_URI') or
            environ.get('RAW_URI')
        )
        if original_path:
            path_only = original_path.split('?')[0]
            environ['PATH_INFO'] = path_only
        elif environ.get('PATH_INFO') in ('/api/index.py', '/api', '/api/'):
            environ['PATH_INFO'] = '/'
        return self.wsgi_app(environ, start_response)

app.wsgi_app = VercelPathFixMiddleware(app.wsgi_app)
