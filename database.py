import sqlite3

conn = sqlite3.connect("fraud.db")

cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS fraud_predictions(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    time_value REAL,
    amount REAL,
    prediction TEXT,
    confidence TEXT
)
""")

conn.commit()

conn.close()

print("Database Created Successfully")