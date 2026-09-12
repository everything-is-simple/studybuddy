"""Migration v15: card review scheduling and request idempotency."""
from __future__ import annotations

import sqlite3


def migrate(connection: sqlite3.Connection) -> None:
    connection.executescript("""
        ALTER TABLE study_cards ADD COLUMN due_at TEXT;
        ALTER TABLE study_cards ADD COLUMN interval_days INTEGER NOT NULL DEFAULT 0
            CHECK(interval_days >= 0);
        ALTER TABLE card_reviews ADD COLUMN idempotency_key TEXT;
        CREATE UNIQUE INDEX card_reviews_idempotency_idx
            ON card_reviews(card_id, idempotency_key)
            WHERE idempotency_key IS NOT NULL;
        CREATE INDEX study_cards_due_idx ON study_cards(status, due_at, updated_at);
        UPDATE study_cards
           SET due_at = COALESCE(due_at, updated_at)
         WHERE status = 'ready';
    """)
