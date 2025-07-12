from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))  # Add this line
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(256), nullable=False)
    points = db.Column(db.Integer, default=0)
    is_admin = db.Column(db.Boolean, default=False)
    items = db.relationship('Item', backref='uploader', lazy=True)


class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50))
    type = db.Column(db.String(50))
    size = db.Column(db.String(20))
    condition = db.Column(db.String(50))
    tags = db.Column(db.String(100))
    image_filename = db.Column(db.String(100))
    uploader_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    status = db.Column(db.String(20), default='available')


class SwapRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey('item.id'), nullable=False)  # item to be received
    requester_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    offered_item_id = db.Column(db.Integer, db.ForeignKey('item.id'), nullable=True)  # item offered in swap
    type = db.Column(db.String(10))  # 'swap' or 'buy'
    status = db.Column(db.String(20), default='pending')

