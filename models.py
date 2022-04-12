import uuid

from app import db
from sqlalchemy.dialects.postgresql import UUID
#Yeah, I'm using a database just for storing an int. Heroku stuff.
class Chapter(db.Model):
    __tablename__ = "chapter"

    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.Integer)
    url = db.Column(db.String())

class MailingList(db.Model):
    __tablename__ = "mailinglist"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    mail = db.Column(db.String())
    validation_key = db.Column(UUID(as_uuid=True), default=uuid.uuid4)
    validated = db.Column(db.Boolean, default=False)