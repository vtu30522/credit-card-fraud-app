import pandas as pd
import joblib

model = joblib.load("final_model.pkl")

df = pd.read_csv("sample_transaction.csv")

predictions = model.predict(df)

probabilities = model.predict_proba(df)

print("Predictions:")
print(predictions)

print("\nConfidence Scores:")
print(probabilities)