class Config:
    SECRET_KEY = 'supermarket-secret-2024'
    SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://root:@localhost/supermarket_db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False