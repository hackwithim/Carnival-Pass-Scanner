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
    Vercel CLI 64+ rewrites backend requests using the destination path (/api/index.py).
    This middleware restores the original request path from HTTP_X_MATCHED_PATH
    so Flask routes all endpoints (/, /api/login, /api/scan, /static/...) properly.
    """
    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        matched = environ.get('HTTP_X_MATCHED_PATH')
        if matched:
            environ['PATH_INFO'] = matched
        elif environ.get('PATH_INFO') in ('/api/index.py', '/api', '/api/'):
            environ['PATH_INFO'] = '/'
        return self.wsgi_app(environ, start_response)

app.wsgi_app = VercelPathFixMiddleware(app.wsgi_app)
