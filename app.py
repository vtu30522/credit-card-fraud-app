from flask import Flask, render_template, request
import pandas as pd
import joblib
import os

from db_operations import (
    save_prediction_history,
    get_all_history,
    delete_history
)

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

    fraud_count = int(sum(predictions))

    total = len(predictions)

    normal_count = total - fraud_count

    fraud_percentage = round(
        (fraud_count / total) * 100,
        2
    )

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
        percentage=fraud_percentage
    )


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
    app.run(debug=True)