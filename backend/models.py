#models.py
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class User(UserMixin, db.Model):
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    avg_rating = db.Column(db.Float, default=0.0)
    num_ratings = db.Column(db.Integer, default=0)
    is_admin = db.Column(db.Boolean, default=False)
    # Relationship to FoodPost
    posts = db.relationship('FoodPost', backref='author', lazy=True)
    # ADD THIS RELATIONSHIP
    requests_made = db.relationship('Request', backref='requester', lazy=True)
    ratings_given = db.relationship('Rating', foreign_keys='Rating.from_user_id', back_populates='rating_by', lazy=True)
    ratings_received = db.relationship('Rating', foreign_keys='Rating.to_user_id', back_populates='rating_for', lazy=True)
    def __repr__(self):
        return f"<User {self.username}>"

# New Model for Food Posts
class FoodPost(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    food_name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    quantity = db.Column(db.String(50), nullable=False)
    
    # Location data
    city = db.Column(db.String(100), nullable=False)
    lat = db.Column(db.Float, nullable=False)
    lon = db.Column(db.Float, nullable=False)
    
    # Image file info
    image_url = db.Column(db.String(255), nullable=False)

    # ADD THIS NEW COLUMN
    status = db.Column(db.String(20), nullable=False, default='available') # available, claimed

    # ADD THIS NEW COLUMN FOR ADMIN VERIFICATION
    approval_status = db.Column(db.String(20), nullable=False, default='pending') # pending, approved, declined

    # ADD THIS NEW COLUMN
    phone_number = db.Column(db.String(20), nullable=False)   

    post_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    # Foreign Key to link to the User
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    # ADD THIS RELATIONSHIP
    requests = db.relationship('Request', backref='food_post', lazy=True, cascade="all, delete-orphan")


    def __repr__(self):
        return f"<FoodPost {self.food_name}>"
    

# ADD THIS ENTIRE NEW CLASS AT THE BOTTOM
class Request(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    status = db.Column(db.String(20), nullable=False, default='pending') # pending, accepted, declined
    request_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    # Foreign Keys
    requester_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    food_id = db.Column(db.Integer, db.ForeignKey('food_post.id'), nullable=False)

    def __repr__(self):
        return f"<Request for post {self.food_id} by user {self.requester_id}>"
    
# ADD THIS ENTIRE NEW CLASS
class Rating(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    score = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text)
    rating_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    # Foreign Keys
    from_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    to_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    request_id = db.Column(db.Integer, db.ForeignKey('request.id'), nullable=False)
    
    # Relationships
    rating_by = db.relationship('User', foreign_keys=[from_user_id])
    rating_for = db.relationship('User', foreign_keys=[to_user_id])
