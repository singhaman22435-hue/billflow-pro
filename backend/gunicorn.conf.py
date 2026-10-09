import multiprocessing
import os

bind = "0.0.0.0:" + os.environ.get("PORT", "5000")

# For Render's free/hobby tier (512MB), we must limit workers to prevent OOM kills.
# gevent with 2 workers can handle 2,000 concurrent connections.
workers = 2
worker_class = 'gevent'
worker_connections = 1000

# Logging
accesslog = '-'
errorlog = '-'
loglevel = 'info'

# Timeout
timeout = 120
