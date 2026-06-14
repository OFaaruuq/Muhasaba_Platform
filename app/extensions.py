from flask_login import LoginManager
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
jwt = JWTManager()

login_manager.login_view = "auth.login"
login_manager.login_message = "يرجى تسجيل الدخول للوصول إلى هذه الصفحة."
login_manager.login_message_category = "warning"
