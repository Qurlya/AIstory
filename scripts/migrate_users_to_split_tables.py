"""Convert legacy monolithic users rows into split user satellite tables.

Run once against the existing MySQL database before deploying the bot version that
uses the new models. Connection settings are read from DB_* env vars, same as the
application.
"""
from __future__ import annotations

import os
from sqlalchemy import create_engine, text


def _sync_db_url() -> str:
    scheme = os.getenv("DB_SCHEME", "mysql+pymysql").replace("+aiomysql", "+pymysql")
    user = os.getenv("DB_USER")
    password = os.getenv("DB_PASS")
    host = os.getenv("DB_HOST")
    port = os.getenv("DB_PORT", "3306")
    name = os.getenv("DB_NAME", "")
    if not host:
        raise RuntimeError("DB_HOST is required")
    return f"{scheme}://{user}:{password}@{host}:{port}/{name}"


DDL = [
    """
    CREATE TABLE IF NOT EXISTS user_event_stats (
        id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
        training_completed_cards INT NOT NULL DEFAULT 0,
        training_completed_full INT NOT NULL DEFAULT 0,
        training_true_cards INT NOT NULL DEFAULT 0,
        intensive_completed_cards INT NOT NULL DEFAULT 0,
        intensive_completed_full INT NOT NULL DEFAULT 0,
        intensive_true_cards INT NOT NULL DEFAULT 0,
        marathon_completed_cards INT NOT NULL DEFAULT 0,
        marathon_completed_full INT NOT NULL DEFAULT 0,
        marathon_true_cards INT NOT NULL DEFAULT 0,
        week_training_completed_cards INT NOT NULL DEFAULT 0,
        week_training_completed_full INT NOT NULL DEFAULT 0,
        week_training_true_cards INT NOT NULL DEFAULT 0,
        week_intensive_completed_cards INT NOT NULL DEFAULT 0,
        week_intensive_completed_full INT NOT NULL DEFAULT 0,
        week_intensive_true_cards INT NOT NULL DEFAULT 0,
        week_marathon_completed_cards INT NOT NULL DEFAULT 0,
        week_marathon_completed_full INT NOT NULL DEFAULT 0,
        week_marathon_true_cards INT NOT NULL DEFAULT 0,
        last_update_info DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS user_culture_stats (
        id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
        culture_completed_cards INT NOT NULL DEFAULT 0,
        culture_completed_full INT NOT NULL DEFAULT 0,
        culture_true_cards INT NOT NULL DEFAULT 0,
        week_culture_completed_cards INT NOT NULL DEFAULT 0,
        week_culture_completed_full INT NOT NULL DEFAULT 0,
        week_culture_true_cards INT NOT NULL DEFAULT 0,
        last_update_info DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS user_streaks (
        id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
        streak_days INT NOT NULL DEFAULT 0,
        last_activity DATETIME NOT NULL DEFAULT '1970-01-01 00:00:00'
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS user_ratings (
        id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
        show_in_rating INT NOT NULL DEFAULT 0,
        display_as INT NOT NULL DEFAULT 1,
        monthly_points FLOAT NOT NULL DEFAULT 0,
        rating_year INT NOT NULL DEFAULT 1970,
        rating_month INT NOT NULL DEFAULT 1
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS user_ad_stats (
        id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
        ad_clicks_total INT NOT NULL DEFAULT 0,
        ad_clicks_week INT NOT NULL DEFAULT 0,
        ad_clicks_month INT NOT NULL DEFAULT 0,
        ad_clicked_once INT NOT NULL DEFAULT 0,
        ad_clicked_week INT NOT NULL DEFAULT 0,
        ad_clicked_month INT NOT NULL DEFAULT 0,
        ad_last_click_at DATETIME NULL
    )
    """,
]

USER_ID_COLUMNS = {
    "event_stats_id": "INT NULL",
    "culture_stats_id": "INT NULL",
    "streak_id": "INT NULL",
    "rating_id": "INT NULL",
    "ad_stats_id": "INT NULL",
}

COPY_SQL = [
    """
    INSERT IGNORE INTO user_event_stats (
        id, training_completed_cards, training_completed_full, training_true_cards,
        intensive_completed_cards, intensive_completed_full, intensive_true_cards,
        marathon_completed_cards, marathon_completed_full, marathon_true_cards,
        week_training_completed_cards, week_training_completed_full, week_training_true_cards,
        week_intensive_completed_cards, week_intensive_completed_full, week_intensive_true_cards,
        week_marathon_completed_cards, week_marathon_completed_full, week_marathon_true_cards,
        last_update_info
    )
    SELECT id, training_completed_cards, training_completed_full, training_true_cards,
        intensive_completed_cards, intensive_completed_full, intensive_true_cards,
        marathon_completed_cards, marathon_completed_full, marathon_true_cards,
        week_training_completed_cards, week_training_completed_full, week_training_true_cards,
        week_intensive_completed_cards, week_intensive_completed_full, week_intensive_true_cards,
        week_marathon_completed_cards, week_marathon_completed_full, week_marathon_true_cards,
        COALESCE(last_update_info, NOW())
    FROM users
    WHERE event_stats_id IS NULL
    """,
    """
    INSERT IGNORE INTO user_culture_stats (
        id, culture_completed_cards, culture_completed_full, culture_true_cards,
        week_culture_completed_cards, week_culture_completed_full, week_culture_true_cards,
        last_update_info
    )
    SELECT id, culture_completed_cards, culture_completed_full, culture_true_cards,
        week_culture_completed_cards, week_culture_completed_full, week_culture_true_cards,
        COALESCE(last_update_info, NOW())
    FROM users
    WHERE culture_stats_id IS NULL
    """,
    """
    INSERT IGNORE INTO user_streaks (id, streak_days, last_activity)
    SELECT id, streak_days, COALESCE(last_activity, '1970-01-01 00:00:00') FROM users
    WHERE streak_id IS NULL
    """,
    """
    INSERT IGNORE INTO user_ratings (id, show_in_rating, display_as, monthly_points, rating_year, rating_month)
    SELECT id, 0, 1, 0, YEAR(CURRENT_DATE), MONTH(CURRENT_DATE) FROM users
    WHERE rating_id IS NULL
    """,
    """
    INSERT IGNORE INTO user_ad_stats (
        id, ad_clicks_total, ad_clicks_week, ad_clicks_month,
        ad_clicked_once, ad_clicked_week, ad_clicked_month, ad_last_click_at
    )
    SELECT id, ad_clicks_total, ad_clicks_week, ad_clicks_month,
        ad_clicked_once, ad_clicked_week, ad_clicked_month, ad_last_click_at
    FROM users
    WHERE ad_stats_id IS NULL
    """,
    """
    UPDATE users
    SET event_stats_id = COALESCE(event_stats_id, id),
        culture_stats_id = COALESCE(culture_stats_id, id),
        streak_id = COALESCE(streak_id, id),
        rating_id = COALESCE(rating_id, id),
        ad_stats_id = COALESCE(ad_stats_id, id)
    """,
]

DROP_OLD_COLUMNS = [
    "training_completed_cards", "training_completed_full", "training_true_cards",
    "intensive_completed_cards", "intensive_completed_full", "intensive_true_cards",
    "marathon_completed_cards", "marathon_completed_full", "marathon_true_cards",
    "week_training_completed_cards", "week_training_completed_full", "week_training_true_cards",
    "week_intensive_completed_cards", "week_intensive_completed_full", "week_intensive_true_cards",
    "week_marathon_completed_cards", "week_marathon_completed_full", "week_marathon_true_cards",
    "culture_completed_cards", "culture_completed_full", "culture_true_cards",
    "week_culture_completed_cards", "week_culture_completed_full", "week_culture_true_cards",
    "streak_days", "last_activity", "last_update_info",
    "ad_clicks_total", "ad_clicks_week", "ad_clicks_month", "ad_clicked_once",
    "ad_clicked_week", "ad_clicked_month", "ad_last_click_at",
]


def main() -> None:
    engine = create_engine(_sync_db_url(), future=True)
    with engine.begin() as conn:
        for statement in DDL:
            conn.execute(text(statement))

        existing_columns = {row[0] for row in conn.execute(text("SHOW COLUMNS FROM users")).all()}
        for column, definition in USER_ID_COLUMNS.items():
            if column not in existing_columns:
                conn.execute(text(f"ALTER TABLE users ADD COLUMN {column} {definition}"))
                existing_columns.add(column)

        for statement in COPY_SQL:
            conn.execute(text(statement))

        existing_columns = {row[0] for row in conn.execute(text("SHOW COLUMNS FROM users")).all()}
        for column in DROP_OLD_COLUMNS:
            if column in existing_columns:
                conn.execute(text(f"ALTER TABLE users DROP COLUMN {column}"))
    print("Users migration completed")


if __name__ == "__main__":
    main()
