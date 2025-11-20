"""
WSGI entry point for the Trainings Backoffice application.

This module provides a custom ASGI-to-WSGI adapter that converts the FastAPI
ASGI application to a WSGI-compatible application for deployment on servers
like AlwaysData that use uWSGI.

Why this approach works:
-----------------------
FastAPI is an ASGI application (async), but uWSGI expects a WSGI application (sync).
This adapter:
1. Converts WSGI environ dict to ASGI scope dict
2. Runs the async ASGI app synchronously using asyncio
3. Collects the response parts (status, headers, body) from ASGI
4. Returns them in WSGI format

This adapter supports standard HTTP request/response patterns for REST APIs.
"""

import asyncio
import sys
from pathlib import Path

# Add the backend directory to the Python path so imports work correctly
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from app.main import app


class ASGItoWSGI:
    """
    Minimal ASGI to WSGI adapter for FastAPI applications.

    Converts async ASGI applications to sync WSGI for deployment on
    traditional WSGI servers like uWSGI.
    """

    def __init__(self, asgi_app):
        self.asgi_app = asgi_app

    def __call__(self, environ, start_response):
        # Build ASGI scope from WSGI environ
        scope = {
            'type': 'http',
            'asgi': {'version': '3.0'},
            'http_version': environ.get('SERVER_PROTOCOL', 'HTTP/1.1').split('/')[1],
            'method': environ['REQUEST_METHOD'],
            'path': environ.get('PATH_INFO', '/'),
            'query_string': environ.get('QUERY_STRING', '').encode('utf-8'),
            'root_path': environ.get('SCRIPT_NAME', ''),
            'scheme': environ.get('wsgi.url_scheme', 'http'),
            'server': (environ.get('SERVER_NAME', ''), int(environ.get('SERVER_PORT', 80))),
            'headers': [],
        }

        # Convert HTTP headers from WSGI environ to ASGI format
        for key, value in environ.items():
            if key.startswith('HTTP_'):
                header_name = key[5:].replace('_', '-').lower().encode('latin-1')
                scope['headers'].append((header_name, value.encode('latin-1')))
            elif key == 'CONTENT_TYPE' and value:
                scope['headers'].append((b'content-type', value.encode('latin-1')))
            elif key == 'CONTENT_LENGTH' and value:
                scope['headers'].append((b'content-length', value.encode('latin-1')))

        # Read request body
        try:
            content_length = int(environ.get('CONTENT_LENGTH', 0) or 0)
        except ValueError:
            content_length = 0

        body = environ['wsgi.input'].read(content_length) if content_length else b''
        body_sent = False

        # Response state
        status_code = None
        response_headers = []
        body_parts = []

        async def receive():
            nonlocal body_sent
            if not body_sent:
                body_sent = True
                return {'type': 'http.request', 'body': body, 'more_body': False}
            return {'type': 'http.disconnect'}

        async def send(message):
            nonlocal status_code, response_headers, body_parts
            if message['type'] == 'http.response.start':
                status_code = message['status']
                response_headers = [
                    (name.decode('latin-1'), value.decode('latin-1'))
                    for name, value in message.get('headers', [])
                ]
            elif message['type'] == 'http.response.body':
                body_parts.append(message.get('body', b''))

        # Run ASGI app synchronously
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(self.asgi_app(scope, receive, send))
        finally:
            loop.close()

        # Map status codes to phrases
        status_phrases = {
            200: 'OK', 201: 'Created', 204: 'No Content',
            301: 'Moved Permanently', 302: 'Found', 304: 'Not Modified',
            400: 'Bad Request', 401: 'Unauthorized', 403: 'Forbidden',
            404: 'Not Found', 405: 'Method Not Allowed', 422: 'Unprocessable Entity',
            500: 'Internal Server Error', 502: 'Bad Gateway', 503: 'Service Unavailable'
        }
        status = f"{status_code} {status_phrases.get(status_code, 'Unknown')}"
        start_response(status, response_headers)
        return body_parts


# Create WSGI-compatible application from FastAPI ASGI app
application = ASGItoWSGI(app)

if __name__ == "__main__":
    # For local development, run with uvicorn (native ASGI server)
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
