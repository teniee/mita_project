
from sqlalchemy.orm import Session
from app.db.models import User
from app.core.session import get_db

def create_test_user():
    db: Session = next(get_db())
    existing = db.query(User).filter(User.email == "test@example.com").first()
    if existing:
        print("Test user already exists.")
        return existing

    user = User(
        email="test@example.com",
        hashed_password="$2b$12$examplehashforpassword",  # assumed bcrypt hash
        full_name="Test User"
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    print(f"Test user created with ID: {user.id}")
    return user

# For manual execution
if __name__ == "__main__":
    create_test_user()
