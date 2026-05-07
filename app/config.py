$config = @'
import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'supermarket-secret-2024'

    if os.environ.get('RAILWAY_ENVIRONMENT') or os.environ.get('RENDER'):
        basedir = os.path.abspath(os.path.dirname(__file__))
        SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(basedir, 'supermarket.db')
    else:
        SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://root:@localhost/supermarket_db'

    SQLALCHEMY_TRACK_MODIFICATIONS = False
'@

$config | Out-File -FilePath "config.py" -Encoding utf8
Write-Host "config.py written!"