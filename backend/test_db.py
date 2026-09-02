from sqlalchemy import text

from database import engine


def test_database_connection_smoke():
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1")).scalar()

    assert result == 1


if __name__ == "__main__":
    test_database_connection_smoke()
    print("Database connection check passed.")
