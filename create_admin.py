from api.app import app, db, User
from datetime import datetime

def create_admin_user():
    with app.app_context():
        # Check if admin already exists
        admin = User.query.filter_by(email='keatonflint@gmail.com').first()
        if admin:
            print("Admin user already exists!")
            return

        # Create admin user
        admin = User(
            email='keatonflint@gmail.com',
            username='admin',
            created_at=datetime.utcnow(),
            email_verified=True
        )
        admin.set_password('Ollieman15!')

        # Add to database
        db.session.add(admin)
        db.session.commit()
        print("Admin user created successfully!")

if __name__ == '__main__':
    create_admin_user() 