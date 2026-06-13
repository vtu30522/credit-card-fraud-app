from flask import Flask, render_template, request
import pandas as pd
import joblib
import os

from db_operations import (
    save_prediction_history,
    get_all_history,
    delete_history
)
import database

app = Flask(__name__)

model = joblib.load("final_model.pkl")

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER


@app.route("/")
def home():
    return render_template("home.html")


@app.route("/upload")
def upload():
    return render_template("upload.html")


@app.route("/predict", methods=["POST"])
def predict():
    try:
        file = request.files["file"]

        if file.filename == "":
            return "No file selected"

        filepath = os.path.join(
            app.config["UPLOAD_FOLDER"],
            file.filename
        )

        file.save(filepath)

        df = pd.read_csv(filepath)

        predictions = model.predict(df)

        # compute probabilities for class 1 (fraud)
        try:
            probs = model.predict_proba(df)[:, 1]
        except Exception:
            probs = None

        fraud_count = int(sum(predictions))

        total = len(predictions)

        normal_count = total - fraud_count

        fraud_percentage = round(
            (fraud_count / total) * 100,
            2
        )

        # aggregate confidence metrics
        if probs is not None:
            avg_confidence = round(float(probs.mean()) * 100, 2)
            max_confidence = round(float(probs.max()) * 100, 2)
        else:
            avg_confidence = None
            max_confidence = None

        save_prediction_history(
            file.filename,
            total,
            fraud_count,
            normal_count
        )

        return render_template(
            "result.html",
            filename=file.filename,
            total=total,
            fraud=fraud_count,
            normal=normal_count,
            percentage=fraud_percentage,
            avg_confidence=avg_confidence,
            max_confidence=max_confidence,
        )
    except Exception:
        import traceback
        traceback.print_exc()
        return "Internal server error", 500


@app.route("/history")
def history():

    records = get_all_history()

    return render_template(
        "history.html",
        records=records
    )


@app.route("/delete/<int:id>")
def delete(id):

    delete_history(id)

    records = get_all_history()

    return render_template(
        "history.html",
        records=records
    )


@app.route("/about")
def about():
    return render_template("about.html")


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=False,
    )
