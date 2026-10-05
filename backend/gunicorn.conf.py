"""Gunicorn settings for the app containers."""

import os

bind = "0.0.0.0:8000"
workers = int(os.environ.get("GUNICORN_WORKERS", "3"))
threads = int(os.environ.get("GUNICORN_THREADS", "2"))
worker_class = "gthread"
timeout = 60
graceful_timeout = 30
keepalive = 5
max_requests = 1000
max_requests_jitter = 100
# Request logs come from our JSON middleware, not Gunicorn.
accesslog = None
errorlog = "-"
loglevel = "warning"
worker_tmp_dir = "/dev/shm"  # noqa: S108 - tmpfs heartbeat files, per Gunicorn docs
forwarded_allow_ips = "*"  # only Caddy can reach the container
