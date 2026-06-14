import sqlite3

DATABASE_PATH = "fraud.db"


def connect_db():
    connection = sqlite3.connect(DATABASE_PATH)
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def create_tables():
    conn = connect_db()
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS prediction_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            total_transactions INTEGER NOT NULL,
            fraud_count INTEGER NOT NULL,
            normal_count INTEGER NOT NULL,
            fraud_percentage REAL NOT NULL,
            prediction_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """
    )

    conn.commit()
    conn.close()


def table_exists(cursor, table_name):
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    )
    return cursor.fetchone() is not None


def column_exists(cursor, table_name, column_name):
    cursor.execute(f"PRAGMA table_info({table_name})")
    return any(row[1] == column_name for row in cursor.fetchall())


def ensure_current_schema():
    conn = connect_db()
    cursor = conn.cursor()

    if table_exists(cursor, "users"):
        if not column_exists(cursor, "users", "password_hash"):
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS users_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL,
                    email TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            cursor.execute(
                "INSERT OR IGNORE INTO users_new (id, username, email, password_hash, created_at)"
                " SELECT id, username, email, password, COALESCE(created_at, CURRENT_TIMESTAMP) FROM users"
            )
            cursor.execute("DROP TABLE users")
            cursor.execute("ALTER TABLE users_new RENAME TO users")
        elif not column_exists(cursor, "users", "created_at"):
            cursor.execute("DROP TABLE IF EXISTS users_new")
            cursor.execute(
                """
                CREATE TABLE users_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL,
                    email TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            cursor.execute(
                "INSERT INTO users_new (id, username, email, password_hash, created_at) "
                "SELECT id, username, email, password_hash, CURRENT_TIMESTAMP "
                "FROM users"
            )
            cursor.execute("DROP TABLE users")
            cursor.execute("ALTER TABLE users_new RENAME TO users")

    if table_exists(cursor, "prediction_history"):
        if not column_exists(cursor, "prediction_history", "user_id"):
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS prediction_history_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    filename TEXT NOT NULL,
                    total_transactions INTEGER NOT NULL,
                    fraud_count INTEGER NOT NULL,
                    normal_count INTEGER NOT NULL,
                    fraud_percentage REAL NOT NULL DEFAULT 0,
                    prediction_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
                """
            )
            cursor.execute(
                "INSERT INTO prediction_history_new (id, user_id, filename, total_transactions, fraud_count, normal_count, fraud_percentage, prediction_date)"
                " SELECT id, NULL, filename, total_transactions, fraud_count, normal_count, COALESCE(fraud_percentage, 0), prediction_date FROM prediction_history"
            )
            cursor.execute("DROP TABLE prediction_history")
            cursor.execute("ALTER TABLE prediction_history_new RENAME TO prediction_history")
        elif not column_exists(cursor, "prediction_history", "fraud_percentage"):
            cursor.execute(
                "ALTER TABLE prediction_history ADD COLUMN fraud_percentage REAL NOT NULL DEFAULT 0"
            )

    conn.commit()
    conn.close()
    create_tables()


if __name__ == "__main__":
    ensure_current_schema()
    print("Database Created Successfully")
