import os
import sys
import tempfile
import asyncio
import pytest

# Add backend directory to sys.path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from app.database.connection import DatabaseManager, get_db
import app.database.connection as db_conn_module


@pytest.fixture
def temp_db():
    """Provides a fresh temporary SQLite database for test isolation."""
    f = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db_path = f.name
    f.close()

    db = DatabaseManager(db_path=db_path)
    old_instance = db_conn_module._db_instance
    db_conn_module._db_instance = db

    yield db

    db_conn_module._db_instance = old_instance
    try:
        os.remove(db_path)
    except Exception:
        pass
