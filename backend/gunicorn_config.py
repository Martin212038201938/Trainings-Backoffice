"""
Gunicorn configuration file for production deployment.

Usage:
    gunicorn -c gunicorn_config.py app.main:app
"""

import multiprocessing
import os

# Server socket
bind = "127.0.0.1:8000"
backlog = 2048

# Worker processes
workers = int(os.getenv("GUNICORN_WORKERS", multiprocessing.cpu_count() * 2 + 1))
worker_class = "uvicorn.workers.UvicornWorker"
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 50
timeout = 120
keepalive = 5

# Logging
accesslog = os.getenv("GUNICORN_ACCESS_LOG", "/home/y-b/trainings-backoffice/logs/access.log")
errorlog = os.getenv("GUNICORN_ERROR_LOG", "/home/y-b/trainings-backoffice/logs/error.log")
loglevel = os.getenv("GUNICORN_LOG_LEVEL", "info")
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process naming
proc_name = "trainings-backoffice"

# Server mechanics
daemon = False
pidfile = "/home/y-b/trainings-backoffice/gunicorn.pid"
user = None
group = None
tmp_upload_dir = None

# SSL (if needed)
# keyfile = "/path/to/key.pem"
# certfile = "/path/to/cert.pem"

# Security
limit_request_line = 4094
limit_request_fields = 100
limit_request_field_size = 8190


def on_starting(server):
    """Called just before the master process is initialized."""
    print(f"Starting Trainings Backoffice with {workers} workers")


def on_reload(server):
    """Called to recycle workers during a reload via SIGHUP."""
    print("Reloading Trainings Backoffice")


def when_ready(server):
    """Called just after the server is started."""
    print("Trainings Backoffice is ready to serve requests")


def worker_int(worker):
    """Called when a worker receives the SIGINT or SIGQUIT signal."""
    print(f"Worker {worker.pid} received SIGINT/SIGQUIT")


def worker_abort(worker):
    """Called when a worker receives the SIGABRT signal."""
    print(f"Worker {worker.pid} received SIGABRT")
