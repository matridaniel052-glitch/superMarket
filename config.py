import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'supermarket-secret-2024'
    
    # Use SQLite for deployment, MySQL for local development
    if os.environ.get('RAILWAY_ENVIRONMENT') or os.environ.get('RENDER'):
        # Production environment (Railpack, Railway, Render, etc.)
        basedir = os.path.abspath(os.path.dirname(__file__))
        SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(basedir, 'supermarket.db')
    else:
        # Local development environment
        SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://root:@localhost/supermarket_db'
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False