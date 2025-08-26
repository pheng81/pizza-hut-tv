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
_cpu = os.cpu_count() or 1
# Default workers: at least 2 to keep one available during GC; cap via env if desired
workers = int(os.getenv("GUNICORN_WORKERS", str(max(2, _cpu))))
# Default threads: 4 per worker handles many concurrent I/O-bound requests
threads = int(os.getenv("GUNICORN_THREADS", "4"))
worker_class = "gthread"
preload_app = False

# Timeouts tuned for larger media and slower networks
timeout = int(os.getenv("GUNICORN_TIMEOUT", "90"))
graceful_timeout = int(os.getenv("GUNICORN_GRACEFUL_TIMEOUT", "30"))
# Longer keepalive helps Cloudflared reuse connections, reducing TLS handshakes
keepalive = int(os.getenv("GUNICORN_KEEPALIVE", "75"))
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

# Kernel sendfile acceleration for static file wrappers
sendfile = True

# Light request recycling by default to keep memory fresh on long runs
if max_requests == 0:
  max_requests = 1000
if max_requests_jitter == 0:
  max_requests_jitter = 100
