"""
WSGI entry point for the Trainings Backoffice application.

This module provides a custom ASGI-to-WSGI adapter that works without external
dependencies like asgiref.wsgi.AsgiToWsgi (which may not be available in older
asgiref versions).

Why this approach works:
-----------------------
FastAPI is an ASGI application (async), but uWSGI expects a WSGI application (sync).
Instead of relying on external adapters that may not be available, we implement
a minimal ASGI-to-WSGI bridge using Python's built-in asyncio module.

The adapter:
1. Converts WSGI environ dict to ASGI scope dict
2. Runs the async ASGI app synchronously using asyncio.run()
3. Collects the response parts (status, headers, body) from ASGI
4. Returns them in WSGI format

This is a simplified adapter suitable for synchronous request/response patterns.
It does not support WebSockets or streaming responses, but works well for REST APIs.
"""

import asyncio
import sys
from pathlib import Path
from io import BytesIO

# Add the backend directory to the Python path so imports work correctly
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from app.main import app


class AsgiToWsgiAdapter:
    """
    Minimal ASGI-to-WSGI adapter without external dependencies.

    This adapter wraps an ASGI application and makes it callable as a WSGI
    application. It uses asyncio.run() to execute the async ASGI app
    synchronously within each request.

    Note: This adapter is designed for simple request/response patterns.
    It does not support:
    - WebSocket connections
    - HTTP/2 server push
    - Streaming responses (response is buffered)
    """

    def __init__(self, asgi_app):
        self.asgi_app = asgi_app

    def __call__(self, environ, start_response):
        """
        WSGI callable interface.

        Args:
            environ: WSGI environment dictionary
            start_response: WSGI start_response callable

        Returns:
            Iterable of response body chunks
        """
        # Convert WSGI environ to ASGI scope
        scope = self._build_scope(environ)

        # Collect response parts
        status_code = 500
        response_headers = []
        body_parts = []

        # Read the request body once and cache it
        request_body = environ.get('wsgi.input', BytesIO()).read() or b''
        body_sent = False

        async def receive():
            """ASGI receive callable - provides request body."""
            nonlocal body_sent
            if not body_sent:
                body_sent = True
                return {
                    'type': 'http.request',
                    'body': request_body,
                    'more_body': False,
                }
            # Subsequent calls return disconnect
            return {
                'type': 'http.disconnect',
            }

        async def send(message):
            """ASGI send callable - collects response parts."""
            nonlocal status_code, response_headers, body_parts

            if message['type'] == 'http.response.start':
                status_code = message['status']
                response_headers = [
                    (name.decode('latin-1') if isinstance(name, bytes) else name,
                     value.decode('latin-1') if isinstance(value, bytes) else value)
                    for name, value in message.get('headers', [])
                ]
            elif message['type'] == 'http.response.body':
                body = message.get('body', b'')
                if body:
                    body_parts.append(body)

        # Execute the async app synchronously
        try:
            # Use asyncio.run() for a clean event loop per request
            asyncio.run(self.asgi_app(scope, receive, send))
        except RuntimeError as e:
            # If there's already a running event loop, create a new one
            if "cannot be called from a running event loop" in str(e):
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(self.asgi_app(scope, receive, send))
                finally:
                    loop.close()
            else:
                raise

        # Build WSGI status string
        status_phrases = {
            200: 'OK', 201: 'Created', 204: 'No Content',
            301: 'Moved Permanently', 302: 'Found', 304: 'Not Modified',
            400: 'Bad Request', 401: 'Unauthorized', 403: 'Forbidden',
            404: 'Not Found', 405: 'Method Not Allowed', 422: 'Unprocessable Entity',
            500: 'Internal Server Error', 502: 'Bad Gateway', 503: 'Service Unavailable',
        }
        status_phrase = status_phrases.get(status_code, 'Unknown')
        status = f'{status_code} {status_phrase}'

        # Call WSGI start_response
        start_response(status, response_headers)

        # Return response body
        return body_parts

    def _build_scope(self, environ):
        """
        Convert WSGI environ to ASGI scope.

        Args:
            environ: WSGI environment dictionary

        Returns:
            ASGI scope dictionary
        """
        # Build headers list
        headers = []
        for key, value in environ.items():
            if key.startswith('HTTP_'):
                # HTTP_X_HEADER -> x-header
                header_name = key[5:].lower().replace('_', '-')
                headers.append((header_name.encode('latin-1'), value.encode('latin-1')))
            elif key == 'CONTENT_TYPE' and value:
                headers.append((b'content-type', value.encode('latin-1')))
            elif key == 'CONTENT_LENGTH' and value:
                headers.append((b'content-length', value.encode('latin-1')))

        # Determine scheme
        scheme = environ.get('wsgi.url_scheme', 'http')
        if environ.get('HTTP_X_FORWARDED_PROTO'):
            scheme = environ['HTTP_X_FORWARDED_PROTO']

        # Build server tuple
        server_name = environ.get('SERVER_NAME', 'localhost')
        server_port = int(environ.get('SERVER_PORT', 80))

        # Build client tuple (if available)
        client = None
        if environ.get('REMOTE_ADDR'):
            client_port = int(environ.get('REMOTE_PORT', 0))
            client = (environ['REMOTE_ADDR'], client_port)

        # Build query string
        query_string = environ.get('QUERY_STRING', '').encode('latin-1')

        # Build path
        path = environ.get('PATH_INFO', '/')
        if not path:
            path = '/'

        return {
            'type': 'http',
            'asgi': {'version': '3.0'},
            'http_version': environ.get('SERVER_PROTOCOL', 'HTTP/1.1').split('/')[-1],
            'method': environ.get('REQUEST_METHOD', 'GET'),
            'scheme': scheme,
            'path': path,
            'query_string': query_string,
            'root_path': environ.get('SCRIPT_NAME', ''),
            'headers': headers,
            'server': (server_name, server_port),
            'client': client,
        }


# Create the WSGI application by wrapping the FastAPI ASGI app
# This is what uWSGI will call for each request
application = AsgiToWsgiAdapter(app)


if __name__ == "__main__":
    # For local development, run with uvicorn (native ASGI server)
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
