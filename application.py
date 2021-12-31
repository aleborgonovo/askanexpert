import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd
from datetime import datetime

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True


# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    user_id = session["user_id"]
    
    cash_amount = db.execute("SELECT cash FROM users WHERE id = ?", user_id)
    shell = db.execute("SELECT users.id as user_id, pl.symbol, sum(pl.shares) as total_shares FROM purchase_log pl LEFT JOIN users USING(username) WHERE user_id = ? GROUP BY 1,2", user_id)
    db.execute("DELETE FROM portfolio where user_id = ?", user_id)

    for row in shell:
        price = float(lookup(row["symbol"])['price'])
        db.execute("INSERT OR REPLACE INTO portfolio (user_id, symbol, shares, current_price, total_value) VALUES (?, ?, ?, ?, ?)", user_id, row["symbol"], row["total_shares"], price, price * row["total_shares"])

    final = db.execute("SELECT * FROM portfolio WHERE user_id = ?", user_id)
    if len(final) == 0:
        stock_value = db.execute("SELECT 0 as stock_value")
    else:
        stock_value = db.execute("SELECT SUM(total_value) as stock_value FROM portfolio WHERE user_id = ?", user_id)
    return render_template("index.html", final = final, stock_value = stock_value, cash_amount = cash_amount)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
    
        symbol = request.form.get("symbol").upper()  # get items from form
        shares = request.form.get("shares")
        info = lookup(symbol)
        if not info:
            return apology("symbol not valid", 400)
        
        elif not shares:
            return apology("must provide # of shares", 400)

        elif not shares.isdigit():
            return apology("must provide # of shares", 400)

        elif int(shares) < 0:
            return apology("must provide positive # of shares", 400)

        info_symbol = info['symbol']  # get items from lookup function
        info_name = info['name']
        current_price = float(lookup(symbol)['price'])
        
        user_id = session["user_id"]  # gets the user_id from the session which is the id in the users table
        
        date = datetime.now()

        if not symbol:
            return apology("must provide symbol", 400)

        rows = db.execute("SELECT * FROM users WHERE id = ?", user_id)
        username = rows[0]["username"]
        
        ending_balance = float(rows[0]["cash"]) - (current_price * int(shares))
        if ending_balance < 0:
            return apology("Not enough money", 403)
        
        db.execute("INSERT INTO purchase_log (username, symbol, shares, price, time) VALUES (?, ?, ?, ?, ?) ", username, symbol, int(shares), current_price, date)
        db.execute("UPDATE users SET cash = ? WHERE username = ?", ending_balance, username)
        
        #TODO TODO TODO TODO TODO: create indexes for table
        
        return redirect("/")
        
    else:
        return render_template("buy.html")

@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    user_id = session["user_id"]
    table = db.execute("SELECT * FROM purchase_log LEFT JOIN users USING(username) WHERE users.id = ?", user_id)
    return render_template("history.html", table = table)

@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":
        ticker = request.form.get("symbol")
        info = lookup(ticker)
        if not info:
            return apology("must return valid ticker", 400)
        return render_template("quoted.html", info = info)
    else:
        return render_template("quote.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":

        # Ensure username was submitted
        username = request.form.get("username")
        rows = db.execute("SELECT * FROM users WHERE username = ?", username)

        if not username:
            return apology("must provide username", 400)
        
        elif len(rows) != 0:  #confirms that only one username with that username
            return apology("username not available", 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 400)
        
        elif not request.form.get("confirmation"):
            return apology("must provide password confirmation", 400)
        
        elif request.form.get("password") != request.form.get("confirmation"):
            return apology("passwords don't match", 400)
        
        hash_password = generate_password_hash(request.form.get("password"))
        db.execute("INSERT INTO users (username, hash) VALUES (?, ?)", username, hash_password)
        return redirect("/")
        
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    
    if request.method == "POST":
        user_id = session["user_id"]
        symbol = request.form.get("symbol")  # get items from form
        shares = int(request.form.get("shares"))
        current_price = float(lookup(symbol)['price'])
        
        user_id = session["user_id"]  # gets the user_id from the session which is the id in the users table
        username_table = db.execute("SELECT * FROM users WHERE id = ?", user_id)
        username = username_table[0]["username"]
        
        date = datetime.now()

        check = db.execute("SELECT symbol, sum(shares) as total_shares_v2 FROM purchase_log LEFT JOIN users USING(username) WHERE users.id = ? AND symbol = ?", user_id, request.form.get("symbol"))
        
        if len(check) == 0:
            return apology("You do not own this company", 400)
        
        elif not shares:
            return apology("must provide # of shares", 400)
        
        elif shares > check[0]["total_shares_v2"]:
            return apology("must provide an amount equal to or less than what you own", 400)
        
        db.execute("INSERT INTO purchase_log (username, symbol, shares, price, time) VALUES (?, ?, ?, ?, ?) ", username, symbol, -shares, current_price, date)
        new_cash = username_table[0]["cash"] + (shares * current_price)
        db.execute("UPDATE users SET cash = ? WHERE username = ?", new_cash, username)
        #update cash position
        return redirect("/")
        
    else:
        user_id = session["user_id"]  # gets the user_id from the session which is the id in the users table
        rows = db.execute("SELECT symbol, sum(shares) as total_shares FROM purchase_log LEFT JOIN users USING(username) WHERE users.id = ? GROUP BY 1", user_id)
        return render_template("sell.html", rows = rows)

def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
