from sqlalchemy import create_engine, func, select
from sqlalchemy.pool import NullPool

from app.config import settings
from app.database import engine


def test_pool_reconnects_after_a_stale_connection() -> None:
    maintenance = create_engine(settings.database_url, poolclass=NullPool)
    engine.dispose()
    try:
        with engine.connect() as connection:
            backend_pid = connection.scalar(select(func.pg_backend_pid()))

        # Terminate only the connection created by this test, once returned to the pool.
        with maintenance.connect() as connection:
            assert connection.scalar(select(func.pg_terminate_backend(backend_pid)))

        with engine.connect() as connection:
            assert connection.scalar(select(1)) == 1
            assert connection.scalar(select(func.pg_backend_pid())) != backend_pid
    finally:
        engine.dispose()
        maintenance.dispose()
