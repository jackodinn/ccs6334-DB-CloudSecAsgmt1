import os
import pyodbc  # type: ignore
import urllib
import uuid
from flask import Flask, render_template, request, redirect, url_for, flash, abort
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
from flask_migrate import Migrate
from itsdangerous import URLSafeTimedSerializer, URLSafeSerializer
from forms import RegistrationForm, LoginForm, ForgotPasswordForm, ResetPasswordForm
from models import User, Profile  # You already have this
from extension import db   # Assuming extension.py initializes db
from functools import wraps
from flask_wtf import CSRFProtect

load_dotenv()

app = Flask(__name__)
# Database configuration for SQL Server using ODBC
connection_params = urllib.parse.quote_plus(
    f"DRIVER={{ODBC Driver 17 for SQL Server}};" # Update driver depends on whatever your system have
    f"SERVER={os.getenv('DB_SERVER')};"
    f"DATABASE={os.getenv('DB_NAME')};"
    f"UID={os.getenv('DB_USER')};"
    f"PWD={os.getenv('DB_PASSWORD')};"
    "Encrypt=yes;"
    "TrustServerCertificate=yes;"
)

# Add this line right after defining connection_params
app.config['SQLALCHEMY_DATABASE_URI'] = f"mssql+pyodbc:///?odbc_connect={connection_params}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'a-strong-default-key')

db.init_app(app)
migrate = Migrate(app, db)
csrf = CSRFProtect(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'      # redirect unauthenticated users
login_manager.login_message_category = 'info'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- Token serializer for password reset ---
def get_reset_token(expires_sec=1800):
    s = URLSafeTimedSerializer(app.config['SECRET_KEY'])
    return s

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            # Return a 403 Forbidden error if not an admin
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

# --- Routes ---
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
        # Check if username or email already exists
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
            flash('Logged in successfully.', 'success')
            # Redirect to the page the user originally wanted, or home
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('home'))
        else:
            flash('Invalid username or password.', 'danger')
    return render_template('login.html', form=form)

@app.route('/logout')
def logout():
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
            # Generate a time‑limited token
            s = get_reset_token()
            token = s.dumps(user.email, salt='password-reset-salt')
            # In a real app, send an email. For development, print the link.
            reset_url = url_for('reset_password', token=token, _external=True)
            print(f"Password reset link for {user.email}: {reset_url}")
            flash(f'A reset link has been sent (dev: {reset_url})', 'info')
        else:
            # Don't reveal whether the email exists
            flash('If that email is registered, you will receive a reset link.', 'info')
        return redirect(url_for('login'))
    return render_template('forgot_password.html', form=form)

@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    s = get_reset_token()
    try:
        email = s.loads(token, salt='password-reset-salt', max_age=1800)  # 30 min
    except:
        flash('The reset link is invalid or has expired.', 'danger')
        return redirect(url_for('forgot_password'))

    form = ResetPasswordForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=email).first()
        if user:
            user.password = generate_password_hash(form.password.data)
            db.session.commit()
            flash('Your password has been updated. You can now log in.', 'success')
            return redirect(url_for('login'))
        else:
            flash('User not found.', 'danger')
            return redirect(url_for('forgot_password'))

    return render_template('reset_password.html', form=form, token=token)

def get_search_token(data: dict) -> str:
    """Encode a dictionary of search parameters into a URL-safe token."""
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

    # Build the data to encode (you can add more fields)
    search_data = {
        'destination': destination,
        'check_in': check_in,
        'guests': guests,
        'query_id': str(uuid.uuid4())[:8]   # optional: add a unique identifier
    }

    token = get_search_token(search_data)
    return redirect(url_for('home_search', token=token))

@app.route('/home/<token>')
def home_search(token):
    s = URLSafeSerializer(app.config['SECRET_KEY'])
    try:
        search_data = s.loads(token)
    except:
        flash('Invalid or malformed search link.', 'danger')
        return redirect(url_for('home'))

    # Here you would normally query your database with these parameters
    # For now, we'll just pass the data to the template to display
    return render_template('search_results.html', search=search_data)

@app.route('/admin')
@login_required
@admin_required
def admin_dashboard():
    # Fetch all users to display in the table
    users = User.query.all()
    return render_template('admin.html', users=users)

@app.route('/admin/toggle-role/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def admin_toggle_role(user_id):
    user = User.query.get_or_404(user_id)
    
    # Prevent an admin from demoting themselves (safety check)
    if user.user_id == current_user.user_id:
        flash("You cannot change your own admin status.", "warning")
        return redirect(url_for('admin_dashboard'))

    # Toggle the boolean
    user.is_admin = not user.is_admin
    db.session.commit()
    
    role = "Admin" if user.is_admin else "Regular User"
    flash(f"User {user.username} has been updated to {role}.", "success")
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete-user/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def admin_delete_user(user_id):
    user = User.query.get_or_404(user_id)

    # Prevent self-deletion
    if user.user_id == current_user.user_id:
        flash("You cannot delete your own admin account.", "danger")
        return redirect(url_for('admin_dashboard'))

    db.session.delete(user)
    db.session.commit()
    
    flash(f"User {user.username} has been deleted.", "info")
    return redirect(url_for('admin_dashboard'))

if __name__ == '__main__':
    # Create tables if they don't exist (for first run)
    with app.app_context():
        db.create_all()
    app.run(debug=True)