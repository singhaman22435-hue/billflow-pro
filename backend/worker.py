import os
import sys
import time
from app import create_app
from scheduler import process_recurring_invoices
from flask_apscheduler import APScheduler

if __name__ == '__main__':
    # Initialize the Flask app context for the worker
    app = create_app()
    app.config['SCHEDULER_API_ENABLED'] = False
    
    with app.app_context():
        print("Starting standalone APScheduler worker for background tasks...")
        
        scheduler = APScheduler()
        scheduler.init_app(app)
        
        # We run the cron job at 1:00 AM daily
        @scheduler.task('cron', id='recurring_invoices_job', hour=1, minute=0)
        def scheduled_task():
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Running scheduled recurring invoices generation...")
            process_recurring_invoices(app)
            
        scheduler.start()
        
        # Keep the main thread alive
        try:
            while True:
                time.sleep(60)
        except (KeyboardInterrupt, SystemExit):
            print("Shutting down worker...")
