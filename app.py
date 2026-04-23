import os
from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv
from flask_migrate import Migrate
from extension import db
from sqlalchemy import MetaData, text

load_dotenv()

app = Flask(__name__)
# Securely construct the connection string using environment variables
app.config['SQLALCHEMY_DATABASE_URI'] = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
migrate = Migrate(app, db)

from models import User, Profile

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/test-db')
def test_db():
    try:
        # Perform a query
        user_count = User.query.count()
        # Pass the result to a template
        return render_template('test-db.html', count=user_count)
    except Exception as e:
        return f"Database connection failed: {str(e)}"

@app.route('/signup')
def signup():
    return render_template('signup.html')

@app.route('/login')
def login():
    return render_template('login.html')

if __name__ == '__main__':
    app.run(debug=True)