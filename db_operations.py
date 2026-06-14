import sqlite3

DATABASE_PATH = "fraud.db"


def get_connection():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def create_user(username, email, password_hash):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO users (username, email, password_hash)
            VALUES (?, ?, ?)
            """,
            (username, email, password_hash),
        )
        conn.commit()
        return cursor.lastrowid
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()


def get_user_by_email(email):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM users WHERE email = ?",
        (email,),
    )
    user = cursor.fetchone()
    conn.close()
    return user


def get_user_by_id(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM users WHERE id = ?",
        (user_id,),
    )
    user = cursor.fetchone()
    conn.close()
    return user


def save_prediction_history(
    user_id,
    filename,
    total_transactions,
    fraud_count,
    normal_count,
    fraud_percentage,
):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO prediction_history
            (user_id, filename, total_transactions, fraud_count, normal_count, fraud_percentage)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (user_id, filename, total_transactions, fraud_count, normal_count, fraud_percentage),
    )
    conn.commit()
    conn.close()


def get_history_for_user(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, filename, total_transactions, fraud_count, normal_count, fraud_percentage, prediction_date
        FROM prediction_history
        WHERE user_id = ?
        ORDER BY id DESC
        """,
        (user_id,),
    )
    records = cursor.fetchall()
    conn.close()
    return records


def get_history_record_by_id(record_id, user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, filename, total_transactions, fraud_count, normal_count, fraud_percentage, prediction_date
        FROM prediction_history
        WHERE id = ? AND user_id = ?
        """,
        (record_id, user_id),
    )
    record = cursor.fetchone()
    conn.close()
    return record


def delete_history_record(record_id, user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM prediction_history WHERE id = ? AND user_id = ?",
        (record_id, user_id),
    )
    conn.commit()
    success = cursor.rowcount > 0
    conn.close()
    return success
