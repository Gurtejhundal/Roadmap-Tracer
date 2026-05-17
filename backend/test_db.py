import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, text


def test_database_connection_smoke():
    load_dotenv()
    url = os.getenv("DATABASE_URL", "sqlite:///./roadmap.db")
    engine = create_engine(url, connect_args={"check_same_thread": False} if "sqlite" in url else {})

    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1")).scalar()

    assert result == 1


if __name__ == "__main__":
    test_database_connection_smoke()
    print("Database connection check passed.")
