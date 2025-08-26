"""
Gunicorn configuration for the Flask app.

Usage on server (example):
  gunicorn -c deploy/gunicorn.conf.py app:app

Key defaults:
  - Binds to 127.0.0.1:5002 (for Cloudflare Tunnel to proxy)
  - Threaded workers for good I/O performance
  - Reasonable timeouts for media streaming
  - Logs to stdout/stderr (systemd captures these)

Environment overrides (optional):
  BIND, GUNICORN_WORKERS, GUNICORN_THREADS, GUNICORN_TIMEOUT,
  GUNICORN_GRACEFUL_TIMEOUT, GUNICORN_KEEPALIVE, GUNICORN_BACKLOG,
  GUNICORN_LOGLEVEL, GUNICORN_ACCESSLOG, GUNICORN_ERRORLOG,
  GUNICORN_MAX_REQUESTS, GUNICORN_MAX_REQUESTS_JITTER
"""

import os


# Network binding (Cloudflared connects to this local address)
bind = os.getenv("BIND", "127.0.0.1:5002")

# Concurrency model: threads are good for Flask + I/O
workers = int(os.getenv("GUNICORN_WORKERS", "3"))
threads = int(os.getenv("GUNICORN_THREADS", "3"))
worker_class = "gthread"
preload_app = False

# Timeouts tuned for larger media and slower networks
timeout = int(os.getenv("GUNICORN_TIMEOUT", "120"))
graceful_timeout = int(os.getenv("GUNICORN_GRACEFUL_TIMEOUT", "30"))
keepalive = int(os.getenv("GUNICORN_KEEPALIVE", "65"))
backlog = int(os.getenv("GUNICORN_BACKLOG", "2048"))

# Logging
loglevel = os.getenv("GUNICORN_LOGLEVEL", "info")
accesslog = os.getenv("GUNICORN_ACCESSLOG", "-")  # '-' = stdout
errorlog = os.getenv("GUNICORN_ERRORLOG", "-")    # '-' = stderr
capture_output = True

# Behind Cloudflare Tunnel / proxies
forwarded_allow_ips = "*"

# Optional: recycle workers to avoid rare leaks
max_requests = int(os.getenv("GUNICORN_MAX_REQUESTS", "0"))
max_requests_jitter = int(os.getenv("GUNICORN_MAX_REQUESTS_JITTER", "0"))
