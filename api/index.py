import sys
import os
import urllib.parse

# Add root project directory to sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from app import app

class VercelPathFixMiddleware:
    """
    Vercel rewrites backend requests using the destination path (/api/index.py).
    Extracts the original request path from query param __path__ or Vercel proxy headers
    so Flask routes all endpoints (/, /api/login, /api/scan, /static/...) accurately.
    """
    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        qs = environ.get('QUERY_STRING', '')
        if '__path__' in qs:
            parsed = urllib.parse.parse_qs(qs, keep_blank_values=True)
            if '__path__' in parsed:
                raw_path = parsed.pop('__path__')[0]
                new_qs = urllib.parse.urlencode([(k, v) for k, vals in parsed.items() for v in vals])
                environ['PATH_INFO'] = raw_path if raw_path.startswith('/') else '/' + raw_path
                environ['QUERY_STRING'] = new_qs
        elif environ.get('PATH_INFO') in ('/api/index.py', '/api', '/api/'):
            environ['PATH_INFO'] = '/'
        return self.wsgi_app(environ, start_response)

app.wsgi_app = VercelPathFixMiddleware(app.wsgi_app)
