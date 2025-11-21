"""Minimal WSGI test for AlwaysData."""

def application(environ, start_response):
    path = environ.get('PATH_INFO', '/')

    status = '200 OK'
    headers = [('Content-Type', 'application/json')]
    start_response(status, headers)

    body = f'{{"status": "ok", "path": "{path}", "message": "WSGI works!"}}'
    return [body.encode('utf-8')]
