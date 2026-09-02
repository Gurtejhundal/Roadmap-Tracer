import os
from pathlib import Path
import tempfile


_temporary_database_dir = None
test_database_url = os.getenv("TRAQU_TEST_DATABASE_URL")

if not test_database_url:
    _temporary_database_dir = tempfile.TemporaryDirectory(prefix="traqu-tests-")
    database_path = Path(_temporary_database_dir.name) / "roadmap-test.db"
    test_database_url = f"sqlite:///{database_path.as_posix()}"

# Set this before pytest imports database.py through any test module. load_dotenv
# does not override an existing value, so a developer database cannot be selected
# accidentally during a test run.
os.environ["DATABASE_URL"] = test_database_url


def pytest_sessionfinish(session, exitstatus):
    try:
        from database import engine

        engine.dispose()
    finally:
        if _temporary_database_dir is not None:
            _temporary_database_dir.cleanup()
