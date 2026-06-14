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
    bootstrap_database()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=app.config.get("FLASK_DEBUG", True))
