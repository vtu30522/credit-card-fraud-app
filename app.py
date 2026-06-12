from flask import Flask, render_template, request, redirect

from db_operations import (
    insert_prediction,
    get_all_predictions,
    delete_prediction
)

app = Flask(__name__)


@app.route("/")
def home():
    return render_template("home.html")


@app.route("/predict", methods=["GET", "POST"])
def predict():

    if request.method == "POST":

        time_value = request.form["Time"]
        amount = request.form["Amount"]

        # Temporary Dummy Prediction
        prediction = "Normal Transaction"
        confidence = "98.50%"

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


import os

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000))
    )