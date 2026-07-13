import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

load_dotenv()

# Prioritize Env Var (Cloud), fallback to Local SQLite.
# Vercel's function filesystem is ephemeral; /tmp keeps preview deploys writable.
if os.getenv("DATABASE_URL"):
    DATABASE_URL = os.getenv("DATABASE_URL")
elif os.getenv("VERCEL"):
    DATABASE_URL = "sqlite:////tmp/roadmap.db"
else:
    DATABASE_URL = "sqlite:///./roadmap.db"

engine = create_engine(
    DATABASE_URL, 
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
