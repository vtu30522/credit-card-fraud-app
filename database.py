import sqlite3

conn = sqlite3.connect("fraud.db")

cursor = conn.cursor()

# Users Table
cursor.execute("""
CREATE TABLE IF NOT EXISTS users(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT,
    email TEXT,
    password TEXT
)
""")

# Prediction History Table
cursor.execute("""
CREATE TABLE IF NOT EXISTS prediction_history(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT,
    total_transactions INTEGER,
    fraud_count INTEGER,
    normal_count INTEGER,
    prediction_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

conn.commit()
conn.close()

print("Database Created Successfully")