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
    Vercel serverless functions handle requests via /api/index.py.
    This middleware extracts the original request path from:
    1. Query param __path__ (passed by vercel.json routes/rewrites)
    2. Vercel proxy headers (HTTP_X_NOW_PATHNAME, HTTP_X_FORWARDED_URI, HTTP_X_MATCHED_PATH)
    3. Direct mapping for root/index requests
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
        elif environ.get('PATH_INFO') in ('/api/index.py', '/api', '/api/', '/api/index'):
            proxy_path = (
                environ.get('HTTP_X_NOW_PATHNAME') or
                environ.get('HTTP_X_FORWARDED_URI') or
                environ.get('HTTP_X_MATCHED_PATH')
            )
            if proxy_path and not proxy_path.startswith('/api/index'):
                environ['PATH_INFO'] = proxy_path.split('?')[0]
            else:
                environ['PATH_INFO'] = '/'

        return self.wsgi_app(environ, start_response)

app.wsgi_app = VercelPathFixMiddleware(app.wsgi_app)

