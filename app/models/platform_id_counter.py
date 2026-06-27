from app.extensions import db


class PlatformIdCounter(db.Model):
    """Atomic sequence for globally unique platform identity numbers."""

    __tablename__ = "platform_id_counter"

    id = db.Column(db.Integer, primary_key=True, default=1)
    next_value = db.Column(db.Integer, nullable=False, default=1)
