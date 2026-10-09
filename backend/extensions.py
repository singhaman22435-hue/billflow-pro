from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_mail import Mail
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect
from flask_caching import Cache

db = SQLAlchemy()
login_manager = LoginManager()
mail = Mail()
migrate = Migrate()
csrf = CSRFProtect()
cache = Cache()

try:
    from authlib.integrations.flask_client import OAuth
    oauth = OAuth()
except ImportError:
    oauth = None
