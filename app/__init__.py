from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from config import Config

db = SQLAlchemy()
login_manager = LoginManager()

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access the system.'

    from app.routes.auth import auth
    from app.routes.products import products
    from app.routes.sales import sales
    from app.routes.suppliers import suppliers
    from app.routes.stock import stock
    from app.routes.reports import reports
    from app.routes.settings import settings
    app.register_blueprint(auth)
    app.register_blueprint(products)
    app.register_blueprint(sales)
    app.register_blueprint(suppliers)
    app.register_blueprint(stock)
    app.register_blueprint(reports)
    app.register_blueprint(settings)

    return app