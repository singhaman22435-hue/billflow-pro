import os
import sys

# Add backend folder to path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend'))

try:
    from backend.app import app
    print("APP LOADED SUCCESSFULLY!")
except Exception as e:
    import traceback
    print("========================================")
    print("ERROR LOADING APP:")
    traceback.print_exc()
    print("========================================")
