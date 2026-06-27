import os

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

from app import create_app, db

app = create_app()


def bootstrap_database():
    """First-run setup: migrations, schema patches, demo seed."""
    from app.utils.database import init_database

    with app.app_context():
        init_database(seed=True)


if __name__ == "__main__":
    with app.app_context():
        from app.models import User
        if User.query.count() == 0:
            bootstrap_database()
    port = int(os.environ.get("PORT", 5000))
    debug = app.config.get("FLASK_DEBUG", False)
    app.run(host="127.0.0.1", port=port, debug=debug)
