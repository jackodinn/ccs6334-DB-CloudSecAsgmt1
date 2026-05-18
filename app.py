from datetime import datetime
import os
import urllib
import uuid
from functools import wraps

import pyodbc  # type: ignore
from flask import Flask, render_template, request, redirect, url_for, flash, abort
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
from flask_migrate import Migrate
from itsdangerous import URLSafeTimedSerializer, URLSafeSerializer
from flask_wtf import CSRFProtect

from forms import RegistrationForm, LoginForm, ForgotPasswordForm, ResetPasswordForm
from models import User, Profile, AuditLog, PendingAdminAction
from extension import db


load_dotenv()

app = Flask(__name__)

connection_params = urllib.parse.quote_plus(
    f"DRIVER={{ODBC Driver 18 for SQL Server}};"
    f"SERVER={os.getenv('DB_SERVER')};"
    f"DATABASE={os.getenv('DB_NAME')};"
    f"UID={os.getenv('DB_USER')};"
    f"PWD={os.getenv('DB_PASSWORD')};"
    "Encrypt=yes;"
    "TrustServerCertificate=yes;"
)

app.config['SQLALCHEMY_DATABASE_URI'] = f"mssql+pyodbc:///?odbc_connect={connection_params}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'a-strong-default-key')
app.config.update(
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
)

db.init_app(app)
migrate = Migrate(app, db)
csrf = CSRFProtect(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


def get_reset_token(expires_sec=1800):
    s = URLSafeTimedSerializer(app.config['SECRET_KEY'])
    return s


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated_function


def save_audit_log(action, details=None, user=None, username=None):
    try:
        log = AuditLog(
            user_id=user.user_id if user else None,
            username=user.username if user else username,
            action=action,
            details=details,
            ip_address=request.remote_addr
        )
        db.session.add(log)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"Audit log error: {e}")


def has_pending_admin_action(action_type, target_user_id):
    return PendingAdminAction.query.filter_by(
        action_type=action_type,
        target_user_id=target_user_id,
        status='PENDING'
    ).first()


@app.route('/')
def home():
    return render_template('home.html')


@app.route('/test-db')
def test_db():
    try:
        user_count = User.query.count()
        return render_template('test-db.html', count=user_count)
    except Exception as e:
        return f"Database connection failed: {str(e)}"


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    form = RegistrationForm()

    if form.validate_on_submit():
        user_exists = User.query.filter_by(username=form.username.data).first()
        email_exists = User.query.filter_by(email=form.email.data).first()

        if user_exists:
            flash('Username already taken.', 'danger')
        elif email_exists:
            flash('Email already registered.', 'danger')
        else:
            hashed_pw = generate_password_hash(form.password.data)
            new_user = User(
                username=form.username.data,
                email=form.email.data,
                password=hashed_pw
            )

            db.session.add(new_user)
            db.session.commit()

            save_audit_log(
                action="REGISTER",
                details=f"New user registered: {new_user.username}",
                user=new_user
            )

            flash('Account created! You can now log in.', 'success')
            return redirect(url_for('login'))

    return render_template('signup.html', form=form)


@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()

    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()

        if user and check_password_hash(user.password, form.password.data):
            login_user(user)

            save_audit_log(
                action="LOGIN_SUCCESS",
                details=f"User {user.username} logged in successfully.",
                user=user
            )

            flash('Logged in successfully.', 'success')
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('home'))

        save_audit_log(
            action="LOGIN_FAILED",
            details=f"Failed login attempt for username: {form.username.data}",
            username=form.username.data
        )
        flash('Invalid username or password.', 'danger')

    return render_template('login.html', form=form)


@app.route('/logout')
@login_required
def logout():
    save_audit_log(
        action="LOGOUT",
        details=f"User {current_user.username} logged out.",
        user=current_user
    )

    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('home'))


@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    form = ForgotPasswordForm()

    if form.validate_on_submit():
        email = form.email.data
        user = User.query.filter_by(email=email).first()

        if user:
            s = get_reset_token()
            token = s.dumps(user.email, salt='password-reset-salt')
            reset_url = url_for('reset_password', token=token, _external=True)
            print(f"Password reset link for {user.email}: {reset_url}")

            save_audit_log(
                action="PASSWORD_RESET_REQUEST",
                details=f"Password reset requested for {user.email}.",
                user=user
            )

            flash(f'A reset link has been sent (dev: {reset_url})', 'info')
        else:
            save_audit_log(
                action="PASSWORD_RESET_REQUEST_UNKNOWN_EMAIL",
                details=f"Password reset requested for unknown email: {email}",
                username=email
            )
            flash('If that email is registered, you will receive a reset link.', 'info')

        return redirect(url_for('login'))

    return render_template('forgot_password.html', form=form)


@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    s = get_reset_token()

    try:
        email = s.loads(token, salt='password-reset-salt', max_age=1800)
    except Exception:
        save_audit_log(
            action="PASSWORD_RESET_INVALID_TOKEN",
            details="Invalid or expired password reset token was used.",
            username="Unknown"
        )
        flash('The reset link is invalid or has expired.', 'danger')
        return redirect(url_for('forgot_password'))

    form = ResetPasswordForm()

    if form.validate_on_submit():
        user = User.query.filter_by(email=email).first()

        if user:
            user.password = generate_password_hash(form.password.data)
            db.session.commit()

            save_audit_log(
                action="PASSWORD_RESET_SUCCESS",
                details=f"Password was reset for user {user.username}.",
                user=user
            )

            flash('Your password has been updated. You can now log in.', 'success')
            return redirect(url_for('login'))

        save_audit_log(
            action="PASSWORD_RESET_USER_NOT_FOUND",
            details=f"Reset token email did not match any user: {email}",
            username=email
        )
        flash('User not found.', 'danger')
        return redirect(url_for('forgot_password'))

    return render_template('reset_password.html', form=form, token=token)


def get_search_token(data: dict) -> str:
    s = URLSafeSerializer(app.config['SECRET_KEY'])
    return s.dumps(data)


@app.route('/search', methods=['GET'])
def search():
    destination = request.args.get('destination', '').strip()
    check_in = request.args.get('check_in', '')
    guests = request.args.get('guests', '').strip()

    if not destination or not check_in:
        flash('Please provide both destination and check-in date.', 'warning')
        return redirect(url_for('home'))

    search_data = {
        'destination': destination,
        'check_in': check_in,
        'guests': guests,
        'query_id': str(uuid.uuid4())[:8]
    }

    token = get_search_token(search_data)
    return redirect(url_for('home_search', token=token))


@app.route('/home/<token>')
def home_search(token):
    s = URLSafeSerializer(app.config['SECRET_KEY'])

    try:
        search_data = s.loads(token)
    except Exception:
        flash('Invalid or malformed search link.', 'danger')
        return redirect(url_for('home'))

    return render_template('search_results.html', search=search_data)


@app.route('/admin')
@login_required
@admin_required
def admin_dashboard():
    users = User.query.all()

    logs = AuditLog.query.order_by(
        AuditLog.created_at.desc()
    ).limit(50).all()

    pending_actions = PendingAdminAction.query.filter_by(
        status='PENDING'
    ).order_by(
        PendingAdminAction.created_at.desc()
    ).all()

    return render_template(
        'admin.html',
        users=users,
        logs=logs,
        pending_actions=pending_actions
    )


@app.route('/admin/toggle-role/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def admin_toggle_role(user_id):
    user = User.query.get_or_404(user_id)

    if user.user_id == current_user.user_id:
        flash("You cannot change your own admin status.", "warning")
        return redirect(url_for('admin_dashboard'))

    # If user is already admin, request DEMOTE approval
    if user.is_admin:
        action_type = "DEMOTE_USER"
        details = f"Request to demote admin {user.username} to regular user."
        success_message = f"Demotion request for {user.username} created. Another admin must approve it."
        audit_action = "DEMOTE_REQUEST_CREATED"
        audit_details = f"Admin {current_user.username} requested to demote {user.username}."

    # If user is normal user, request PROMOTE approval
    else:
        action_type = "PROMOTE_USER"
        details = f"Request to promote user {user.username} to admin."
        success_message = f"Promotion request for {user.username} created. Another admin must approve it."
        audit_action = "PROMOTE_REQUEST_CREATED"
        audit_details = f"Admin {current_user.username} requested to promote {user.username} to Admin."

    existing_request = has_pending_admin_action(action_type, user.user_id)

    if existing_request:
        flash(
            f"A {action_type} request for {user.username} is already pending approval.",
            "warning"
        )
        return redirect(url_for('admin_dashboard'))

    pending = PendingAdminAction(
        action_type=action_type,
        target_user_id=user.user_id,
        target_username=user.username,
        target_email=user.email,
        requested_by_id=current_user.user_id,
        requested_by_username=current_user.username,
        details=details
    )

    db.session.add(pending)
    db.session.commit()

    save_audit_log(
        action=audit_action,
        details=audit_details,
        user=current_user
    )

    flash(success_message, "info")
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/delete-user/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def admin_delete_user(user_id):
    user = User.query.get_or_404(user_id)

    if user.user_id == current_user.user_id:
        save_audit_log(
            action="ADMIN_DELETE_BLOCKED",
            details=f"Admin {current_user.username} attempted to delete their own account.",
            user=current_user
        )
        flash("You cannot delete your own admin account.", "danger")
        return redirect(url_for('admin_dashboard'))

    existing_request = has_pending_admin_action("DELETE_USER", user.user_id)

    if existing_request:
        flash(
            f"A delete request for {user.username} is already pending approval.",
            "warning"
        )
        return redirect(url_for('admin_dashboard'))

    pending = PendingAdminAction(
        action_type="DELETE_USER",
        target_user_id=user.user_id,
        target_username=user.username,
        target_email=user.email,
        requested_by_id=current_user.user_id,
        requested_by_username=current_user.username,
        details=f"Request to delete user {user.username}."
    )

    db.session.add(pending)
    db.session.commit()

    save_audit_log(
        action="DELETE_REQUEST_CREATED",
        details=f"Admin {current_user.username} requested to delete user {user.username}.",
        user=current_user
    )

    flash(
        f"Delete request for {user.username} created. Another admin must approve it.",
        "info"
    )
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/approve-action/<int:request_id>', methods=['POST'])
@login_required
@admin_required
def approve_admin_action(request_id):
    pending = PendingAdminAction.query.get_or_404(request_id)

    if pending.status != "PENDING":
        flash("This request has already been processed.", "warning")
        return redirect(url_for('admin_dashboard'))

    if pending.requested_by_id == current_user.user_id:
        save_audit_log(
            action="APPROVAL_BLOCKED",
            details=f"Admin {current_user.username} tried to approve their own request.",
            user=current_user
        )
        flash("You cannot approve your own request. Another admin must approve it.", "danger")
        return redirect(url_for('admin_dashboard'))

    target_user = User.query.get(pending.target_user_id)

    if not target_user:
        pending.status = "CANCELLED"
        pending.completed_at = datetime.utcnow()
        db.session.commit()
        flash("Target user no longer exists. Request cancelled.", "warning")
        return redirect(url_for('admin_dashboard'))

    if target_user.user_id == current_user.user_id:
        flash("You cannot approve an action against your own account.", "danger")
        return redirect(url_for('admin_dashboard'))

    if pending.action_type == "DEMOTE_USER":
        target_user.is_admin = False

        pending.status = "APPROVED"
        pending.approved_by_id = current_user.user_id
        pending.approved_by_username = current_user.username
        pending.completed_at = datetime.utcnow()

        db.session.commit()

        save_audit_log(
            action="DEMOTE_APPROVED",
            details=f"Admin {current_user.username} approved demotion of {target_user.username}.",
            user=current_user
        )

        flash(f"{target_user.username} has been demoted after second admin approval.", "success")
        return redirect(url_for('admin_dashboard'))
    
    if pending.action_type == "PROMOTE_USER":
        target_user.is_admin = True

        pending.status = "APPROVED"
        pending.approved_by_id = current_user.user_id
        pending.approved_by_username = current_user.username
        pending.completed_at = datetime.utcnow()

        db.session.commit()

        save_audit_log(
            action="PROMOTE_APPROVED",
            details=f"Admin {current_user.username} approved promotion of {target_user.username} to Admin.",
            user=current_user
        )

        flash(f"{target_user.username} has been promoted to Admin after second admin approval.", "success")
        return redirect(url_for('admin_dashboard'))
    
    
    if pending.action_type == "DELETE_USER":
        deleted_username = target_user.username
        deleted_email = target_user.email
        deleted_user_id = target_user.user_id

        pending.status = "APPROVED"
        pending.approved_by_id = current_user.user_id
        pending.approved_by_username = current_user.username
        pending.completed_at = datetime.utcnow()

        # Remove references from audit_logs before deleting user
        AuditLog.query.filter_by(user_id=deleted_user_id).update(
            {"user_id": None},
            synchronize_session=False
        )

        # Remove ALL references from pending_admin_actions before deleting user
        PendingAdminAction.query.filter_by(target_user_id=deleted_user_id).update(
            {"target_user_id": None},
            synchronize_session=False
        )

        PendingAdminAction.query.filter_by(requested_by_id=deleted_user_id).update(
            {"requested_by_id": None},
            synchronize_session=False
        )

        PendingAdminAction.query.filter_by(approved_by_id=deleted_user_id).update(
            {"approved_by_id": None},
            synchronize_session=False
        )

        # Cancel other pending requests related to this deleted user
        other_pending_actions = PendingAdminAction.query.filter(
            PendingAdminAction.target_username == deleted_username,
            PendingAdminAction.request_id != pending.request_id,
            PendingAdminAction.status == "PENDING"
        ).all()

        for action in other_pending_actions:
            action.status = "CANCELLED"
            action.completed_at = datetime.utcnow()

        db.session.delete(target_user)
        db.session.commit()

        save_audit_log(
            action="DELETE_APPROVED",
            details=f"Admin {current_user.username} approved deletion of {deleted_username} ({deleted_email}).",
            user=current_user
        )

        flash(f"User {deleted_username} has been deleted after second admin approval.", "success")
        return redirect(url_for('admin_dashboard'))


@app.route('/admin/reject-action/<int:request_id>', methods=['POST'])
@login_required
@admin_required
def reject_admin_action(request_id):
    pending = PendingAdminAction.query.get_or_404(request_id)

    if pending.status != "PENDING":
        flash("This request has already been processed.", "warning")
        return redirect(url_for('admin_dashboard'))

    if pending.requested_by_id == current_user.user_id:
        flash("You cannot reject your own request. Another admin must review it.", "danger")
        return redirect(url_for('admin_dashboard'))

    pending.status = "REJECTED"
    pending.approved_by_id = current_user.user_id
    pending.approved_by_username = current_user.username
    pending.completed_at = datetime.utcnow()

    db.session.commit()

    save_audit_log(
        action="ADMIN_ACTION_REJECTED",
        details=f"Admin {current_user.username} rejected {pending.action_type} request for {pending.target_username}.",
        user=current_user
    )

    flash("Admin action request has been rejected.", "info")
    return redirect(url_for('admin_dashboard'))


if __name__ == '__main__':
    with app.app_context():
        db.create_all()

    app.run(debug=True, ssl_context=('localhost.pem', 'localhost-key.pem'))
