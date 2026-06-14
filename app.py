import os
import functools
from datetime import timedelta

import numpy as np
import pandas as pd
import joblib
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from database import ensure_current_schema
from db_operations import (
    create_user,
    get_user_by_email,
    get_user_by_id,
    save_prediction_history,
    get_history_for_user,
    get_history_record_by_id,
    delete_history_record,
)

UPLOAD_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {"csv"}
REQUIRED_COLUMNS = ["Time"] + [f"V{i}" for i in range(1, 29)] + ["Amount"]

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.secret_key = os.environ.get("SECRET_KEY", "supersecretkey123")
app.permanent_session_lifetime = timedelta(days=7)

ensure_current_schema()

try:
    model = joblib.load("final_model.pkl")
except FileNotFoundError:
    raise RuntimeError(
        "Missing final_model.pkl. Place the trained Random Forest model in the project root."
    )
except Exception as exc:
    raise RuntimeError(
        "Unable to load final_model.pkl. Verify the model file and package dependencies."
    ) from exc


def login_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if "user_id" not in session:
            flash("Please sign in to continue.", "warning")
            return redirect(url_for("login"))
        return view(**kwargs)

    return wrapped_view


def current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    return get_user_by_id(user_id)


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def build_history_stats(records):
    total_transactions = sum(record["total_transactions"] for record in records)
    total_fraud = sum(record["fraud_count"] for record in records)
    total_normal = sum(record["normal_count"] for record in records)
    fraud_rate = round((total_fraud / total_transactions) * 100, 2) if total_transactions else 0
    return total_transactions, total_fraud, total_normal, fraud_rate


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not username or not email or not password:
            flash("Please complete all required fields.", "danger")
            return render_template("register.html")

        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return render_template("register.html")

        if get_user_by_email(email):
            flash("That email is already registered.", "danger")
            return render_template("register.html")

        password_hash = generate_password_hash(password)
        user_id = create_user(username, email, password_hash)

        if user_id is None:
            flash("Unable to create your account. Please try again.", "danger")
            return render_template("register.html")

        flash("Account created successfully. Please sign in.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("home"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = get_user_by_email(email)

        if user is None or not check_password_hash(user["password_hash"], password):
            flash("Invalid email or password.", "danger")
            return render_template("login.html")

        session.permanent = True
        session["user_id"] = user["id"]
        session["username"] = user["username"]

        flash(f"Welcome back, {user['username']}!", "success")
        return redirect(url_for("home"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out successfully.", "success")
    return redirect(url_for("login"))


@app.route("/")
@login_required
def home():
    user = current_user()
    records = get_history_for_user(user["id"])

    total_files = len(records)
    total_transactions, total_fraud, total_normal, fraud_rate = build_history_stats(records)

    recent = records[:7]
    chart_labels = [row["prediction_date"].split(" ")[0] for row in recent]
    fraud_values = [row["fraud_count"] for row in recent]
    volume_values = [row["total_transactions"] for row in recent]

    return render_template(
        "home.html",
        username=user["username"],
        total_files=total_files,
        total_transactions=total_transactions,
        total_fraud=total_fraud,
        total_normal=total_normal,
        fraud_rate=fraud_rate,
        chart_labels=chart_labels,
        fraud_values=fraud_values,
        volume_values=volume_values,
    )


@app.route("/upload")
@login_required
def upload():
    return render_template("upload.html")


@app.route("/predict", methods=["POST"])
@login_required
def predict():
    uploaded_file = request.files.get("file")
    if uploaded_file is None or uploaded_file.filename == "":
        flash("Please choose a CSV file to upload.", "danger")
        return redirect(url_for("upload"))

    if not allowed_file(uploaded_file.filename):
        flash("Only CSV files are supported.", "danger")
        return redirect(url_for("upload"))

    filename = secure_filename(uploaded_file.filename)
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    uploaded_file.save(filepath)

    try:
        df = pd.read_csv(filepath)
    except Exception:
        flash(
            "Unable to read the uploaded CSV file. Please verify the file format.",
            "danger",
        )
        return redirect(url_for("upload"))

    if df.empty:
        flash("Uploaded file is empty. Please provide a valid CSV file.", "danger")
        return redirect(url_for("upload"))

    missing_columns = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing_columns:
        flash(
            "CSV is missing required columns: {}".format(
                ", ".join(missing_columns)
            ),
            "danger",
        )
        return redirect(url_for("upload"))

    try:
        df = df[REQUIRED_COLUMNS]
        predictions = np.asarray(model.predict(df))
    except Exception:
        flash(
            "Unable to process the uploaded CSV. Verify the file contains the required transaction features.",
            "danger",
        )
        return redirect(url_for("upload"))

    try:
        probabilities = model.predict_proba(df)[:, 1]
    except Exception:
        probabilities = None

    total = len(predictions)
    fraud_count = int(np.sum(predictions == 1))
    normal_count = total - fraud_count
    fraud_percentage = round((fraud_count / total) * 100, 2) if total else 0

    fraud_transactions = []
    if fraud_count:
        fraud_rows = df[predictions == 1]
        for row_index, row in fraud_rows.iterrows():
            confidence = (
                f"{round(float(probabilities[row_index]) * 100, 2)}%"
                if probabilities is not None
                else "N/A"
            )
            fraud_transactions.append(
                {
                    "transaction_number": int(row_index) + 1
                    if isinstance(row_index, int)
                    else row_index,
                    "time": row["Time"],
                    "amount": row["Amount"],
                    "prediction": "Fraud",
                    "confidence": confidence,
                }
            )

    user = current_user()
    save_prediction_history(
        user_id=user["id"],
        filename=filename,
        total_transactions=total,
        fraud_count=fraud_count,
        normal_count=normal_count,
        fraud_percentage=fraud_percentage,
    )

    return render_template(
        "result.html",
        filename=filename,
        total=total,
        fraud=fraud_count,
        normal=normal_count,
        percentage=fraud_percentage,
        fraud_transactions=fraud_transactions,
        has_fraud=bool(fraud_transactions),
    )


@app.route("/history", defaults={"record_id": None})
@app.route("/history/<int:record_id>")
@login_required
def history(record_id):
    user = current_user()
    records = get_history_for_user(user["id"])
    selected_record = None

    if record_id is not None:
        selected_record = get_history_record_by_id(record_id, user["id"])
        if selected_record is None:
            flash("Record not found or does not belong to your account.", "warning")
            return redirect(url_for("history"))

    return render_template(
        "history.html",
        records=records,
        selected_record=selected_record,
    )


@app.route("/delete/<int:record_id>")
@login_required
def delete(record_id):
    user = current_user()
    deleted = delete_history_record(record_id, user["id"])

    if deleted:
        flash("Prediction record deleted successfully.", "success")
    else:
        flash("Unable to remove that record.", "danger")

    return redirect(url_for("history"))


@app.route("/analysis")
@login_required
def analysis():
    user = current_user()
    records = get_history_for_user(user["id"])

    total_files = len(records)
    total_transactions, total_fraud, total_normal, fraud_rate = build_history_stats(records)
    average_fraud_rate = round(
        sum(record["fraud_percentage"] for record in records) / total_files, 2
    ) if total_files else 0

    recent = records[:8]
    chart_labels = [row["prediction_date"].split(" ")[0] for row in recent]
    fraud_values = [row["fraud_count"] for row in recent]
    normal_values = [row["normal_count"] for row in recent]
    fraud_vs_normal = [total_fraud, total_normal]

    return render_template(
        "analysis.html",
        total_files=total_files,
        total_transactions=total_transactions,
        total_fraud=total_fraud,
        average_fraud_rate=average_fraud_rate,
        fraud_rate=fraud_rate,
        chart_labels=chart_labels,
        fraud_values=fraud_values,
        normal_values=normal_values,
        fraud_vs_normal=fraud_vs_normal,
    )


@app.route("/about")
@login_required
def about():
    return render_template("about.html")


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=False,
    )
