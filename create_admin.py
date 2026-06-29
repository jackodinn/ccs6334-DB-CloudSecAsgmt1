from getpass import getpass

from werkzeug.security import generate_password_hash

from app import app
from extension import db
from models import User


def ask_non_empty(prompt: str) -> str:
    """Prompt until the user enters a non-empty value."""
    while True:
        value = input(prompt).strip()
        if value:
            return value
        print("This field cannot be empty.")


def create_or_promote_admin() -> None:
    """Create a new admin account or promote an existing user."""
    with app.app_context():
        try:
            username = ask_non_empty("Admin username: ")

            existing_user = User.query.filter_by(username=username).first()

            if existing_user:
                if existing_user.is_admin:
                    print(f"'{username}' is already an administrator.")
                    return

                confirm = input(
                    f"User '{username}' already exists. Promote this user to admin? [y/N]: "
                ).strip().lower()

                if confirm != "y":
                    print("No changes were made.")
                    return

                existing_user.is_admin = True
                existing_user.is_frozen = False
                existing_user.failed_login_attempts = 0
                db.session.commit()

                print(f"User '{username}' has been promoted to administrator.")
                print("Log out and log in again to display the Admin Dashboard.")
                return

            email = ask_non_empty("Admin email: ")

            if "@" not in email:
                print("Invalid email address.")
                return

            existing_email = User.query.filter_by(email=email).first()
            if existing_email:
                print(
                    f"The email '{email}' is already registered to "
                    f"username '{existing_email.username}'."
                )
                return

            password = getpass("Admin password (minimum 8 characters): ")
            confirm_password = getpass("Confirm admin password: ")

            if len(password) < 8:
                print("Password must contain at least 8 characters.")
                return

            if password != confirm_password:
                print("Passwords do not match.")
                return

            admin = User(
                username=username,
                email=email,
                password=generate_password_hash(password),
                is_admin=True,
                is_frozen=False,
                failed_login_attempts=0,
            )

            db.session.add(admin)
            db.session.commit()

            print(f"Administrator '{username}' was created successfully.")

        except Exception as error:
            db.session.rollback()
            print(f"Failed to create administrator: {error}")


if __name__ == "__main__":
    create_or_promote_admin()
