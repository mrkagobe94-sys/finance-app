from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_bcrypt import Bcrypt
import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from datetime import datetime, timedelta
import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

bcrypt = Bcrypt(app)

# DATABASE CONNECTION
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("WARNING: DATABASE_URL not set!")

def get_db_connection():
    return psycopg2.connect(
        DATABASE_URL,
        sslmode="require"
    )

# --- UTILITIES ---

CURRENCY_RATES = {
    'UGX': 1, 'USD': 3700, 'EUR': 4000, 'GBP': 4700, 'JPY': 25
}

def convert_to_ugx(amount, currency):
    rate = CURRENCY_RATES.get(currency, 1)
    return float(amount) * rate

# --- ROUTES ---

@app.route('/')
def home():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/register', methods=['GET','POST'])
def register():

    if request.method == 'POST':

        try:
            username = request.form.get('username')
            password_raw = request.form.get('password')

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

@app.route('/login', methods=['GET','POST'])
def login():

    if request.method == 'POST':

        username = request.form['username']
        password = request.form['password']

        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("SELECT * FROM users WHERE username=%s", [username])
        user = cur.fetchone()

        cur.close()
        conn.close()

        if user and bcrypt.check_password_hash(user[2], password):

            session['user_id'] = user[0]
            session['username'] = user[1]

            return redirect(url_for('dashboard'))

        else:
            return "Invalid Credentials"

    return render_template('login.html')

if __name__ == '__main__':
    app.run(debug=True)