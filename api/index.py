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
    Vercel serverless functions handle requests via /api/index.py.
    When crawlers or rewrites target /api/index.py or /api, this middleware
    maps it cleanly to root ('/'), while letting all other paths
    (/api/stats, /api/login, /api/scan, /static/...) route directly through Flask.
    """
    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        if environ.get('PATH_INFO') in ('/api/index.py', '/api', '/api/', '/api/index'):
            environ['PATH_INFO'] = '/'
        return self.wsgi_app(environ, start_response)

app.wsgi_app = VercelPathFixMiddleware(app.wsgi_app)
