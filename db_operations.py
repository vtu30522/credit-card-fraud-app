import sqlite3


def insert_prediction(
    time_value,
    amount,
    prediction,
    confidence
):

    conn = sqlite3.connect("fraud.db")

    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO fraud_predictions
    (
        time_value,
        amount,
        prediction,
        confidence
    )
    VALUES (?, ?, ?, ?)
    """,
    (
        time_value,
        amount,
        prediction,
        confidence
    ))

    conn.commit()
    conn.close()


def get_all_predictions():

    conn = sqlite3.connect("fraud.db")

    cursor = conn.cursor()

    cursor.execute("""
    SELECT * FROM fraud_predictions
    """)

    records = cursor.fetchall()

    conn.close()

    return records


def delete_prediction(id):

    conn = sqlite3.connect("fraud.db")

    cursor = conn.cursor()

    cursor.execute(
        "DELETE FROM fraud_predictions WHERE id=?",
        (id,)
    )

    conn.commit()
    conn.close()