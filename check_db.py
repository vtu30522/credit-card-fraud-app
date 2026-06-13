import sqlite3

conn = sqlite3.connect("fraud.db")

cursor = conn.cursor()

cursor.execute(
    "SELECT name FROM sqlite_master WHERE type='table';"
)

tables = cursor.fetchall()

print("Tables Found:")
print(tables)

conn.close()