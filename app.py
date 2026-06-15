import os
import functools
import time
import io
import csv
from datetime import timedelta

import numpy as np
import pandas as pd
import joblib
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file, abort
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

# Pure-Python ReportLab dependencies for styling and canvas tracking
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

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
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10 MB max upload size
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


def current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    return get_user_by_id(user_id)


# FIXED: Validates both session presence AND database existence to prevent NoneType 500 crashes
def login_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if "user_id" not in session or current_user() is None:
            session.clear()  # Wipes stale cookies cleanly if the DB dropped your user row
            flash("Please sign in to continue.", "warning")
            return redirect(url_for("login"))
        return view(**kwargs)

    return wrapped_view


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@app.errorhandler(413)
def request_entity_too_large(error):
    flash("The uploaded file is too large. Please upload a CSV file under 10 MB.", "danger")
    return redirect(url_for("upload"))


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
    if session.get("user_id") and current_user() is not None:
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
    if os.path.exists(filepath):
        base, ext = os.path.splitext(filename)
        filename = f"{base}_{int(time.time())}{ext}"
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    
    uploaded_file.save(filepath)

    try:
        df = pd.read_csv(filepath)
    except Exception:
        flash("Unable to read the uploaded CSV file. Please verify the file format.", "danger")
        return redirect(url_for("upload"))

    if df.empty:
        flash("Uploaded file is empty. Please provide a valid CSV file.", "danger")
        return redirect(url_for("upload"))

    missing_columns = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing_columns:
        flash("CSV is missing required columns: {}".format(", ".join(missing_columns)), "danger")
        return redirect(url_for("upload"))

    try:
        df = df[REQUIRED_COLUMNS]
        predictions = np.asarray(model.predict(df))
    except Exception:
        flash("Unable to process the uploaded CSV. Verify the file contains the required transaction features.", "danger")
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
                if probabilities is not None else "N/A"
            )
            fraud_transactions.append({
                "transaction_number": int(row_index) + 1 if isinstance(row_index, int) else row_index,
                "time": row["Time"],
                "amount": row["Amount"],
                "prediction": "Fraud",
                "confidence": confidence,
            })

    user = current_user()
    save_prediction_history(
        user_id=user["id"],
        filename=filename,
        total_transactions=total,
        fraud_count=fraud_count,
        normal_count=normal_count,
        fraud_percentage=fraud_percentage,
    )

    session["last_report"] = {
        "filename": filename,
        "total": total,
        "fraud": fraud_count,
        "normal": normal_count,
        "percentage": fraud_percentage,
        "fraud_transactions": fraud_transactions,
    }

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


@app.route("/download-sample")
@login_required
def download_sample():
    sample_file = "sample_transaction.csv"
    sample_path = os.path.join(app.root_path, sample_file)
    if not os.path.exists(sample_path):
        abort(404)
    return send_file(sample_path, as_attachment=True, download_name=sample_file)


@app.route("/download-report")
@login_required
def download_report():
    last_report = session.get("last_report")
    if not last_report:
        flash("No prediction report is currently available for download.", "warning")
        return redirect(url_for("home"))

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40
    )
    
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=24,
        leading=28,
        textColor=colors.HexColor('#0f172a'),
        spaceAfter=4
    )
    
    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#64748b'),
        spaceAfter=15
    )
    
    section_heading = ParagraphStyle(
        'SectionHeading',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=14,
        leading=18,
        textColor=colors.HexColor('#1e293b'),
        spaceBefore=15,
        spaceAfter=10
    )
    
    cell_text = ParagraphStyle(
        'CellText',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=13,
        textColor=colors.HexColor('#334155'),
        alignment=1
    )
    
    cell_header = ParagraphStyle(
        'CellHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9.5,
        leading=13,
        textColor=colors.HexColor('#1e293b')
    )

    story = []
    story.append(Paragraph("Transaction Risk Analysis Report", title_style))
    story.append(Paragraph(f"Dataset Target: {last_report['filename']}", subtitle_style))
    story.append(Spacer(1, 10))
    
    metrics_data = [
        [
            Paragraph("<b>{}</b><br/><font color='#64748b'>TOTAL LOGS</font>".format(last_report['total']), cell_text),
            Paragraph("<b><font color='#ef4444'>{}</font></b><br/><font color='#64748b'>FRAUD FLAGGED</font>".format(last_report['fraud']), cell_text),
            Paragraph("<b><font color='#10b981'>{}</font></b><br/><font color='#64748b'>NORMAL SAFE</font>".format(last_report['normal']), cell_text),
            Paragraph("<b>{}%</b><br/><font color='#64748b'>RISK DENSITY</font>".format(last_report['percentage']), cell_text)
        ]
    ]
    
    metrics_table = Table(metrics_data, colWidths=[130, 130, 130, 130])
    metrics_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8fafc')),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('PADDING', (0, 0), (-1, -1), 12),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#e2e8f0')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0'))
    ]))
    story.append(metrics_table)
    story.append(Spacer(1, 20))
    
    story.append(Paragraph("Identified Threat Anomalies", section_heading))
    
    if last_report['fraud_transactions']:
        table_content = [[
            Paragraph("Tx ID", cell_header),
            Paragraph("Time Offset", cell_header),
            Paragraph("Amount Value", cell_header),
            Paragraph("System Verdict", cell_header),
            Paragraph("Confidence Vector", cell_header)
        ]]
        
        for tx in last_report['fraud_transactions']:
            table_content.append([
                Paragraph(f"#{tx['transaction_number']}", cell_text),
                Paragraph(f"{tx['time']}s", cell_text),
                Paragraph(f"${float(tx['amount']):.2f}", cell_text),
                Paragraph("<font color='#ef4444'><b>CRITICAL</b></font>", cell_text),
                Paragraph(tx['confidence'], cell_text)
            ])
            
        data_table = Table(table_content, colWidths=[80, 100, 110, 110, 120])
        t_style = [
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f1f5f9')),
            ('PADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            ('TOPPADDING', (0, 0), (-1, 0), 10),
            ('LINEBELOW', (0, 0), (-1, 0), 1.5, colors.HexColor('#cbd5e1')),
            ('LINEBELOW', (0, 1), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]
        for i in range(1, len(table_content)):
            if i % 2 == 0:
                t_style.append(('BACKGROUND', (0, i), (-1, i), colors.HexColor('#f8fafc')))
                
        data_table.setStyle(TableStyle(t_style))
        story.append(data_table)
    else:
        clean_style = ParagraphStyle(
            'CleanStyle',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=10,
            textColor=colors.HexColor('#166534'),
            alignment=1
        )
        clean_content = [[Paragraph("<b>System Scan Secure:</b> No target fraudulent vector sequences matching risk indexes identified in this transaction trace.", clean_style)]]
        clean_table = Table(clean_content, colWidths=[520])
        clean_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f0fdf4')),
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#bbf7d0')),
            ('PADDING', (0, 0), (-1, -1), 16)
        ]))
        story.append(clean_table)

    def add_footer(canvas, doc):
        canvas.saveState()
        canvas.setFont('Helvetica', 8)
        canvas.setFillColor(colors.HexColor('#64748b'))
        canvas.drawString(40, 30, "FRAUDEX Network Integrity Management Suite")
        canvas.drawRightString(doc.pagesize[0] - 40, 30, f"Page {doc.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=add_footer, onLaterPages=add_footer)
    buffer.seek(0)
    
    return send_file(
        buffer,
        as_attachment=True,
        download_name=f"fraud_report_{last_report['filename']}.pdf",
        mimetype="application/pdf"
    )


@app.route("/download-history-report/<int:record_id>")
@login_required
def download_history_report(record_id):
    user = current_user()
    record = get_history_record_by_id(record_id, user["id"])
    if record is None:
        flash("History record not found.", "warning")
        return redirect(url_for("history"))

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40
    )
    
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'HistTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=22,
        leading=26,
        textColor=colors.HexColor('#0f172a'),
        spaceAfter=4
    )
    
    subtitle_style = ParagraphStyle(
        'HistSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=13,
        textColor=colors.HexColor('#64748b'),
        spaceAfter=20
    )
    
    cell_text = ParagraphStyle(
        'HistCellText',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#334155'),
        alignment=1
    )

    story = []
    story.append(Paragraph("Archived Scan Summary Log", title_style))
    story.append(Paragraph(f"Record Identifier Reference: #{record['id']}  |  Processed On: {record['prediction_date']}", subtitle_style))
    story.append(Spacer(1, 10))
    story.append(Paragraph(f"<b>Dataset Target Filename:</b> {record['filename']}", ParagraphStyle('FN', parent=styles['Normal'], fontSize=10, spaceAfter=15)))
    
    metrics_data = [
        [
            Paragraph("<b>{}</b><br/><font color='#64748b'>TOTAL</font>".format(record['total_transactions']), cell_text),
            Paragraph("<b><font color='#ef4444'>{}</font></b><br/><font color='#64748b'>FRAUD</font>".format(record['fraud_count']), cell_text),
            Paragraph("<b><font color='#10b981'>{}</font></b><br/><font color='#64748b'>NORMAL</font>".format(record['normal_count']), cell_text),
            Paragraph("<b>{}%</b><br/><font color='#64748b'>RISK RATE</font>".format(record['fraud_percentage']), cell_text)
        ]
    ]
    
    metrics_table = Table(metrics_data, colWidths=[130, 130, 130, 130])
    metrics_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8fafc')),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('PADDING', (0, 0), (-1, -1), 14),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#e2e8f0')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0'))
    ]))
    story.append(metrics_table)

    def add_footer(canvas, doc):
        canvas.saveState()
        canvas.setFont('Helvetica', 8)
        canvas.setFillColor(colors.HexColor('#64748b'))
        canvas.drawString(40, 30, "FRAUDEX Archived Security Database Logs Summary")
        canvas.drawRightString(doc.pagesize[0] - 40, 30, f"Page {doc.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=add_footer, onLaterPages=add_footer)
    buffer.seek(0)
    
    return send_file(
        buffer,
        as_attachment=True,
        download_name=f"history_report_{record['id']}.pdf",
        mimetype="application/pdf"
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