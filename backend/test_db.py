import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()
url = os.getenv("DATABASE_URL")
print(f"Connecting to: {url.split('@')[1] if '@' in url else 'LOCAL'}")

try:
    engine = create_engine(url)
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1"))
        print("Success!", result.fetchall())
except Exception as e:
    print("Failed:", e)
