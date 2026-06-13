import sqlite3


def save_prediction_history(
    filename,
    total_transactions,
    fraud_count,
    normal_count
):
    conn = sqlite3.connect("fraud.db")

    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO prediction_history
    (
        filename,
        total_transactions,
        fraud_count,
        normal_count
    )
    VALUES (?, ?, ?, ?)
    """,
    (
        filename,
        total_transactions,
        fraud_count,
        normal_count
    ))

    conn.commit()
    conn.close()


def get_all_history():

    conn = sqlite3.connect("fraud.db")

    cursor = conn.cursor()

    cursor.execute("""
    SELECT * FROM prediction_history
    ORDER BY id DESC
    """)

    records = cursor.fetchall()

    conn.close()

    return records


def delete_history(record_id):

    conn = sqlite3.connect("fraud.db")

    cursor = conn.cursor()

    cursor.execute(
        "DELETE FROM prediction_history WHERE id=?",
        (record_id,)
    )

    conn.commit()
    conn.close()