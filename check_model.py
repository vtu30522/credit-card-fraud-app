import joblib

model = joblib.load("final_model.pkl")

print("Model Loaded Successfully")
print("Number of Features:", model.n_features_in_)