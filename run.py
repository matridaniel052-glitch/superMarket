from app import create_app, db
from app.models import User

app = create_app()

with app.app_context():
    db.create_all()
    if not User.query.filter_by(email='admin@supermart.com').first():
        admin = User(full_name='Admin User', email='admin@supermart.com', role='admin')
        admin.set_password('admin123')
        db.session.add(admin)
        db.session.commit()
        print("Default admin created: admin@supermart.com / admin123")

if __name__ == '__main__':
    app.run(debug=True)