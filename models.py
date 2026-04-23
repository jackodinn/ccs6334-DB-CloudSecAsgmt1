from extension import db

class User(db.Model):
    __tablename__ = 'users'
    user_id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False) # Store hashed passwords!
    is_admin = db.Column(db.Boolean, default=False)
    
    # Relationship to Profile
    profile = db.relationship('Profile', backref='user', uselist=False)

class Profile(db.Model):
    __tablename__ = 'profiles'
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), primary_key=True)
    display_name = db.Column(db.String(100))
    profile_img_path = db.Column(db.String(255))