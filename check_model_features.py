import joblib

model = joblib.load("final_model.pkl")

print("Model Type:", type(model))

try:
    print("\nFeature Names:")
    print(model.feature_names_in_)
except:
    print("\nFeature names not available")