import pytesseract
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

from flask import Flask, render_template, request, redirect, session, flash, send_from_directory
import sqlite3
import os
import smtplib
import random
from email.mime.text import MIMEText
from werkzeug.utils import secure_filename
from transformers import pipeline
from PIL import Image
import json
import re

app = Flask(__name__)
app.secret_key = "EXTREME_SMART_MEDIA_GUARD"

# ================= LOAD AI =================

print("Loading AI Models...")
toxicity_model = pipeline("text-classification",
                          model="unitary/toxic-bert",
                          framework="pt")

nsfw_model = pipeline("image-classification",
                      model="Falconsai/nsfw_image_detection",
                      framework="pt")

print("AI READY")

# ================= CONFIG =================

SENDER_EMAIL = "nityasree202005@gmail.com"
APP_PASSWORD = "zinntszwfnblmvtx"

UPLOAD_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "mp4", "docx"}

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# ================= DATABASE =================

def init_db():
    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE,
        username TEXT,
        password TEXT,
        verified INTEGER DEFAULT 0
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        content TEXT,
        filename TEXT,
        score INTEGER,
        categories TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    conn.commit()
    conn.close()

init_db()

# ================= OTP =================

def send_otp(email, otp):
    msg = MIMEText(f"Your OTP is: {otp}")
    msg["Subject"] = "Smart Media Guard OTP"
    msg["From"] = SENDER_EMAIL
    msg["To"] = email

    server = smtplib.SMTP("smtp.gmail.com", 587)
    server.starttls()
    server.login(SENDER_EMAIL, APP_PASSWORD)
    server.send_message(msg)
    server.quit()

# ================= FILE CHECK =================

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

# ================= EXTREME ANALYSIS =================

def analyze_content(content, filename):

    categories = {
        "Privacy Leaks": 100,
        "Hate Speech": 100,
        "Nudity/Explicit": 100,
        "Violence": 100,
        "Sensitive Topics": 100
    }

    full_text = content or ""

    # OCR
    if filename and filename.lower().endswith(("png","jpg","jpeg")):
        try:
            img = Image.open(os.path.join(app.config["UPLOAD_FOLDER"], filename))
            full_text += " " + pytesseract.image_to_string(img)
        except:
            pass

    text = full_text.lower()

    # 🔥 EXTREME RULE ENGINE
    suicide_words = ["suicide","kill myself","end my life","self harm","hang myself","overdose"]
    violence_words = ["kill","murder","rape","assault","hit","beat","gun","threaten"]
    drug_words = ["heroin","inject","dealer"]
    sexual_words = ["rape","sexual assault","molest"]
    eating_words = ["anorexia","thinspiration","starve"]

    if any(w in text for w in suicide_words):
        categories["Sensitive Topics"] = 5
        categories["Violence"] = 20

    if any(w in text for w in violence_words):
        categories["Violence"] = 10

    if any(w in text for w in drug_words):
        categories["Sensitive Topics"] = 15

    if any(w in text for w in sexual_words):
        categories["Sensitive Topics"] = 5

    if any(w in text for w in eating_words):
        categories["Sensitive Topics"] = 25

    # Privacy Regex
    if re.search(r"\d{4}-\d{4}-\d{4}-\d{4}", text):
        categories["Privacy Leaks"] = 5

    if re.search(r"\d{3}-\d{2}-\d{4}", text):
        categories["Privacy Leaks"] = 5

    if re.search(r"\b\d{10}\b", text):
        categories["Privacy Leaks"] = 20

    # BERT
    try:
        result = toxicity_model(full_text[:512])[0]
        if result["label"] == "toxic":
            drop = int(result["score"] * 80)
            categories["Hate Speech"] = max(0, 100 - drop)
    except:
        pass

    # NSFW
    if filename and filename.lower().endswith(("png","jpg","jpeg")):
        try:
            img = Image.open(os.path.join(app.config["UPLOAD_FOLDER"], filename))
            result = nsfw_model(img)[0]
            if result["label"].lower() == "nsfw":
                categories["Nudity/Explicit"] = 5
        except:
            pass

    final_score = sum(categories.values()) // len(categories)
    return final_score, categories

# ================= ROUTES =================

@app.route("/")
def home():
    return redirect("/login")

# REGISTER
@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
        email = request.form["email"]
        username = request.form["username"]
        password = request.form["password"]

        # Check if already exists
        conn = sqlite3.connect("database.db")
        c = conn.cursor()
        c.execute("SELECT id FROM users WHERE email=?", (email,))
        existing = c.fetchone()
        conn.close()

        if existing:
            flash("Email already registered. Please login.")
            return redirect("/login")

        otp = str(random.randint(100000,999999))
        session["otp"] = otp
        session["temp_user"] = {"email":email,"username":username,"password":password}

        send_otp(email, otp)
        return redirect("/verify")

    return render_template("register.html")

# VERIFY
@app.route("/verify", methods=["GET","POST"])
def verify():
    if request.method == "POST":

        if request.form.get("otp") == session.get("otp"):

            user_data = session.get("temp_user")
            if not user_data:
                return redirect("/register")

            conn = sqlite3.connect("database.db")
            c = conn.cursor()

            c.execute("""
            INSERT INTO users (email,username,password,verified)
            VALUES (?,?,?,1)
            """,(user_data["email"],user_data["username"],user_data["password"]))
            conn.commit()

            # Fetch ID
            c.execute("SELECT id FROM users WHERE email=?", (user_data["email"],))
            user = c.fetchone()
            conn.close()

            session.clear()
            session["user_id"] = user[0]

            return redirect("/dashboard")

        else:
            flash("Invalid OTP")

    return render_template("verify_otp.html")

# LOGIN
@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        conn = sqlite3.connect("database.db")
        c = conn.cursor()
        c.execute("SELECT id FROM users WHERE email=? AND password=? AND verified=1",
                  (email,password))
        user = c.fetchone()
        conn.close()

        if user:
            session["user_id"] = user[0]
            return redirect("/dashboard")

        flash("Invalid login")

    return render_template("login.html")

# DASHBOARD
@app.route("/dashboard", methods=["GET","POST"])
def dashboard():

    if "user_id" not in session:
        return redirect("/login")

    if request.method == "POST":

        content = request.form.get("content")
        file = request.files.get("file")
        filename = None

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))

        score, categories = analyze_content(content, filename)

        conn = sqlite3.connect("database.db")
        c = conn.cursor()
        c.execute("""
        INSERT INTO posts (user_id,content,filename,score,categories)
        VALUES (?,?,?,?,?)
        """,(session["user_id"],content,filename,score,json.dumps(categories)))
        conn.commit()
        conn.close()

        return render_template("result.html",
                               score=score,
                               categories=categories,
                               filename=filename)

    return render_template("dashboard.html")

# HISTORY
@app.route("/history")
def history():
    if "user_id" not in session:
        return redirect("/login")

    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute("SELECT content,filename,score,created_at FROM posts WHERE user_id=? ORDER BY created_at DESC",
              (session["user_id"],))
    posts = c.fetchall()
    conn.close()

    return render_template("history.html", posts=posts)

# ANALYTICS
@app.route("/analytics")
def analytics():
    if "user_id" not in session:
        return redirect("/login")

    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute("SELECT AVG(score), COUNT(*) FROM posts WHERE user_id=?",
              (session["user_id"],))
    data = c.fetchone()
    conn.close()

    avg_score = data[0] if data[0] else 0
    total_posts = data[1]

    return render_template("analytics.html",
                           avg_score=avg_score,
                           total_posts=total_posts)

@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

if __name__ == "__main__":
    app.run(debug=True)
