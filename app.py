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

# SUPABASE DATABASE CONNECTION
DATABASE_URL = os.getenv("DATABASE_URL")

def get_db_connection():
    return psycopg2.connect(DATABASE_URL)


# --- AI & CURRENCY UTILITIES ---

CURRENCY_RATES = {
    'UGX': 1, 'USD': 3700, 'EUR': 4000, 'GBP': 4700, 'JPY': 25
}

def convert_to_ugx(amount, currency):
    rate = CURRENCY_RATES.get(currency, 1)
    return float(amount) * rate


def ai_predict_expenses(user_id):
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT date, amount, currency FROM transactions WHERE user_id = %s", [user_id])
    data = cur.fetchall()

    cur.close()
    conn.close()

    if not data or len(data) < 3:
        return "Not enough data (need 3+ entries) to create a meaningful AI prediction."

    df = pd.DataFrame(data, columns=['date', 'amount', 'currency'])
    df['amount_ugx'] = df.apply(lambda x: convert_to_ugx(x['amount'], x['currency']), axis=1)
    df['date'] = pd.to_datetime(df['date'])
    df['day_ordinal'] = df['date'].map(datetime.toordinal)

    model = LinearRegression()
    X = df[['day_ordinal']]
    y = df['amount_ugx']
    model.fit(X, y)

    future_date = datetime.now() + timedelta(days=30)
    prediction = model.predict([[future_date.toordinal()]])

    return f"Based on your trends, predicted daily spending next month is around {int(prediction[0]):,} UGX."


def ai_categorize_transaction(description, user_id):

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT description, category 
        FROM transactions 
        WHERE user_id = %s 
        AND description IS NOT NULL 
        AND category IS NOT NULL
    """, [user_id])

    data = cur.fetchall()

    cur.close()
    conn.close()

    if len(data) < 10:
        return None

    df = pd.DataFrame(data, columns=['description', 'category'])

    vectorizer = TfidfVectorizer(stop_words='english')
    X_vectorized = vectorizer.fit_transform(df['description'])

    model = LogisticRegression(max_iter=500)
    model.fit(X_vectorized, df['category'])

    prediction = model.predict(vectorizer.transform([description]))[0]

    return prediction


# ROUTES

@app.route('/')
def home():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/register', methods=['GET','POST'])
def register():

    if request.method == 'POST':

        username = request.form['username']
        password = bcrypt.generate_password_hash(request.form['password']).decode('utf-8')

        conn = get_db_connection()
        cur = conn.cursor()

        try:

            cur.execute(
                "INSERT INTO users (username,password) VALUES (%s,%s)",
                (username,password)
            )

            conn.commit()

        except:
            return "Username already exists!"

        finally:
            cur.close()
            conn.close()

        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/login', methods=['GET','POST'])
def login():

    if request.method == 'POST':

        username = request.form['username']
        password = request.form['password']

        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute(
            "SELECT * FROM users WHERE username=%s",
            [username]
        )

        user = cur.fetchone()

        cur.close()
        conn.close()

        if user and bcrypt.check_password_hash(user[2],password):

            session['user_id'] = user[0]
            session['username'] = user[1]

            return redirect(url_for('dashboard'))

        else:

            return "Invalid Credentials"

    return render_template('login.html')


@app.route('/dashboard')
def dashboard():

    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute(
        "SELECT * FROM transactions WHERE user_id=%s ORDER BY date DESC",
        [user_id]
    )

    transactions = cur.fetchall()

    total_spent = sum([
        convert_to_ugx(t[2],t[3]) for t in transactions
    ])

    ai_msg = ai_predict_expenses(user_id)

    cur.execute(
        "SELECT category,amount,currency,start_date,end_date FROM budgets WHERE user_id=%s",
        [user_id]
    )

    raw_budgets = cur.fetchall()

    budget_statuses = []

    for category,budget_amount,budget_currency,start_date,end_date in raw_budgets:

        budget_ugx = convert_to_ugx(budget_amount,budget_currency)

        spent_ugx = 0

        for t in transactions:

            if t[4] == category and start_date <= t[6] <= end_date:

                spent_ugx += convert_to_ugx(t[2],t[3])

        remaining = budget_ugx - spent_ugx

        budget_statuses.append({
            'category': category,
            'budget': f"{budget_currency} {budget_amount:,.2f}",
            'spent_ugx': spent_ugx,
            'remaining_ugx': remaining,
            'status': 'safe' if remaining >= 0 else 'overspent'
        })

    cur.close()
    conn.close()

    return render_template(
        'dashboard.html',
        transactions=transactions,
        total_spent=total_spent,
        ai_msg=ai_msg,
        user=session['username'],
        budget_statuses=budget_statuses
    )


@app.route('/add_transaction',methods=['POST'])
def add_transaction():

    if 'user_id' not in session:
        return redirect(url_for('login'))

    amount = request.form['amount']
    currency = request.form['currency']
    category = request.form['category']
    desc = request.form['description']
    date = request.form['date']

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute(
        """INSERT INTO transactions 
        (user_id,amount,currency,category,description,date)
        VALUES (%s,%s,%s,%s,%s,%s)""",
        (session['user_id'],amount,currency,category,desc,date)
    )

    conn.commit()

    cur.close()
    conn.close()

    return redirect(url_for('dashboard'))


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


if __name__ == '__main__':
    app.run(debug=True)