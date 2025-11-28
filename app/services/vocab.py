import sqlite3
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


class VocabService:
    def __init__(self, db_path="vocab.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize the SQLite database and create the table if it doesn't exist."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # We use a compound primary key (user_id, language, word)
                # to ensure a user has unique progress for each word per language.
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS user_vocab (
                        user_id TEXT,
                        language TEXT,
                        word TEXT,
                        level INTEGER,
                        last_updated TIMESTAMP,
                        PRIMARY KEY (user_id, language, word)
                    )
                """)
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")

    def get_user_word_level(self, user_id: str, word: str, language: str) -> int:
        """
        Fetch SRS level for a word from SQLite.
        Returns 0 if the word is not found.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT level FROM user_vocab WHERE user_id=? AND language=? AND word=?",
                    (user_id, language, word),
                )
                row = cursor.fetchone()
                return row[0] if row else 0
        except Exception as e:
            logger.error(f"Error fetching word level: {e}")
            return 0

    def update_word_level(self, user_id: str, word: str, language: str, new_level: int):
        """
        Update progress in SQLite using an UPSERT (Insert or Replace).

        NOTE: The argument is named 'new_level' to match your main.py call.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                # SQLite 'INSERT OR REPLACE' acts as an Upsert.
                # If the Primary Key (user_id, language, word) exists, it replaces the row.
                conn.execute(
                    """
                    INSERT OR REPLACE INTO user_vocab (user_id, language, word, level, last_updated)
                    VALUES (?, ?, ?, ?, ?)
                """,
                    (user_id, language, word, new_level, datetime.now()),
                )

                conn.commit()
                logger.info(f"Updated vocab: {word} ({language}) -> Level {new_level}")
        except Exception as e:
            logger.error(f"Error updating word level: {e}")
            raise e

    # Alias for compatibility if your main.py calls update_word_progress elsewhere
    def update_word_progress(
        self, user_id: str, word: str, language: str, new_level: int
    ):
        return self.update_word_level(user_id, word, language, new_level)


# Create a singleton instance to be imported
vocab_service = VocabService()
