import os
import sys

# Ensure backend directory is in path for imports to work
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend'))

from backend.app import app

# Vercel Serverless Function entrypoint
if __name__ == '__main__':
    app.run()
