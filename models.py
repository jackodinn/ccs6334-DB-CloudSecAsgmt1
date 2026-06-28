from flask_login import UserMixin
from extension import db
from datetime import datetime


class User(db.Model, UserMixin):
    __tablename__ = 'users'

    user_id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)

    failed_login_attempts = db.Column(db.Integer, default=0)
    is_frozen = db.Column(db.Boolean, default=False)

    profile = db.relationship('Profile', backref='user', uselist=False)

    def get_id(self):
        return str(self.user_id)


class Profile(db.Model):
    __tablename__ = 'profiles'

    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), primary_key=True)
    display_name = db.Column(db.String(100))
    profile_img_path = db.Column(db.String(255))


class AuditLog(db.Model):
    __tablename__ = 'audit_logs'

    log_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=True)
    username = db.Column(db.String(50), nullable=True)
    action = db.Column(db.String(100), nullable=False)
    details = db.Column(db.String(255), nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref='audit_logs')


class PendingAdminAction(db.Model):
    __tablename__ = 'pending_admin_actions'

    request_id = db.Column(db.Integer, primary_key=True)
    action_type = db.Column(db.String(50), nullable=False)

    target_user_id = db.Column(
        db.Integer,
        db.ForeignKey('users.user_id'),
        nullable=True
    )
    target_username = db.Column(db.String(50), nullable=False)
    target_email = db.Column(db.String(100), nullable=True)

    requested_by_id = db.Column(
        db.Integer,
        db.ForeignKey('users.user_id'),
        nullable=True
    )
    requested_by_username = db.Column(db.String(50), nullable=False)

    approved_by_id = db.Column(
        db.Integer,
        db.ForeignKey('users.user_id'),
        nullable=True
    )
    approved_by_username = db.Column(db.String(50), nullable=True)

    status = db.Column(db.String(30), default='PENDING')
    details = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)

    target_user = db.relationship('User', foreign_keys=[target_user_id])
    requested_by = db.relationship('User', foreign_keys=[requested_by_id])
    approved_by = db.relationship('User', foreign_keys=[approved_by_id])
