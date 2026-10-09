from functools import wraps
from flask import flash, redirect, url_for, request
from flask_login import current_user

def role_required(*roles):
    """
    Decorator to restrict access to certain roles.
    Example: @role_required('owner', 'admin')
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for('auth.login', next=request.url))
            if current_user.role not in roles:
                flash('You do not have permission to access this page.', 'danger')
                return redirect(url_for('dashboard.index'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator
