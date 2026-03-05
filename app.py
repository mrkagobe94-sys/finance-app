from flask import Flask, render_template, request, redirect, url_for, session
from flask_bcrypt import Bcrypt
import psycopg2
import os
from dotenv import load_dotenv
from urllib.parse import urlparse

load_dotenv()

app = Flask(__name__)
app.secret_key = "your_secret_key_here"

bcrypt = Bcrypt(app)

# ----------------------------
# DATABASE CONNECTION (FIXED)
# ----------------------------

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise Exception("DATABASE_URL is not set in environment variables")

def get_db_connection():
    result = urlparse(DATABASE_URL)

    return psycopg2.connect(
        host=result.hostname,
        database=result.path[1:],
        user=result.username,
        password=result.password,
        port=result.port,
        sslmode="require"
    )

# ----------------------------
# ROUTES
# ----------------------------

@app.route('/')
def home():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():

    if request.method == 'POST':

        try:
            username = request.form.get('username')
            password_raw = request.form.get('password')

            if not username or not password_raw:
                return "Missing username or password", 400

            password = bcrypt.generate_password_hash(password_raw).decode('utf-8')

            conn = get_db_connection()
            cur = conn.cursor()

            cur.execute(
                "INSERT INTO users (username, password) VALUES (%s, %s)",
                (username, password)
            )

            conn.commit()
            cur.close()
            conn.close()

            return redirect(url_for('login'))

        except Exception as e:
            return f"REGISTER ERROR: {str(e)}", 500

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():

    if request.method == 'POST':

        username = request.form.get('username')
        password = request.form.get('password')

        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute(
            "SELECT * FROM users WHERE username=%s",
            (username,)
        )

        user = cur.fetchone()

        cur.close()
        conn.close()

        if user and bcrypt.check_password_hash(user[2], password):

            session['user_id'] = user[0]
            session['username'] = user[1]

            return redirect(url_for('dashboard'))

        return "Invalid Credentials"

    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    return f"Welcome {session['username']}! App is working."

# ----------------------------

if __name__ == "__main__":
    app.run(debug=True)