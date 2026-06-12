from flask import Flask, render_template, request, redirect

from db_operations import (
    insert_prediction,
    get_all_predictions,
    delete_prediction
)

import os

app = Flask(__name__)


@app.route("/")
def home():
    return render_template("home.html")


@app.route("/predict", methods=["GET", "POST"])
def predict():

    if request.method == "POST":

        time_value = float(request.form["Time"])
        amount = float(request.form["Amount"])

        # -----------------------------
        # RULE-BASED FRAUD LOGIC
        # -----------------------------
        score = 0

        # Rule 1: Amount-based risk
        if amount > 50000:
            score += 2
        elif amount > 20000:
            score += 1

        # Rule 2: Time-based risk
        if time_value < 1000:
            score += 1
        elif time_value > 150000:
            score += 2

        # -----------------------------
        # FINAL DECISION
        # -----------------------------
        if score >= 3:
            prediction = "Fraud Transaction"
            confidence = "91.25%"
        elif score == 2:
            prediction = "Suspicious Transaction"
            confidence = "85.40%"
        else:
            prediction = "Normal Transaction"
            confidence = "97.80%"

        # Save to database
        insert_prediction(
            time_value,
            amount,
            prediction,
            confidence
        )

        return render_template(
            "result.html",
            prediction=prediction,
            confidence=confidence,
            time_value=time_value,
            amount=amount
        )

    return render_template("predict.html")


@app.route("/history")
def history():

    records = get_all_predictions()

    return render_template(
        "history.html",
        records=records
    )


@app.route("/delete/<int:id>")
def delete(id):

    delete_prediction(id)

    return redirect("/history")


@app.route("/about")
def about():
    return render_template("about.html")


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000))
    )