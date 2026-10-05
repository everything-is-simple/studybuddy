"""S1 Today read-only pending-items projection."""
import sqlite3

from fastapi import HTTPException, Query

from ..repositories.connection import connect
from ..repositories.today import get_daily_pending_items


def register_routes(app, context):
    @app.get('/api/today/pending-items')
    def pending_items(date: str | None = Query(default=None, max_length=10),
                      timezone: str | None = Query(default=None, max_length=100)):
        try:
            with connect(app.state.config.database_path) as conn:
                conn.execute('BEGIN')
                return get_daily_pending_items(conn, project_id=app.state.config.project_id,
                                               target_date=date, timezone_name=timezone)
        except ValueError:
            raise HTTPException(status_code=400, detail='today_invalid_date_or_timezone') from None
        except sqlite3.Error:
            raise HTTPException(status_code=500, detail='today_pending_items_failed') from None
    return context
