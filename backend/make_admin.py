from app import create_app
from extensions import db
from models.user import User

app = create_app()

with app.app_context():
    user_email = input("Enter your email address to make Super Admin: ")
    user = User.query.filter_by(email=user_email).first()
    
    if user:
        user.is_super_admin = True
        db.session.commit()
        print(f"Success! {user.email} is now a Super Admin.")
    else:
        print("User not found! Please check the email and try again.")
