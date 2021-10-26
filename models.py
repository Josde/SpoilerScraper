from app import db

#Yeah, I'm using a database just for storing an int. Heroku stuff.
class Chapter(db.Model):
    __tablename__ = "chapter"

    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.Integer)
    url = db.Column(db.String())