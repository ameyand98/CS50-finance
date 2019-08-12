import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

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

# Configure session to use filesystem (store on disk), (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""

    # look up the current user
    user = db.execute("SELECT cash FROM users WHERE id = :user_id", user_id=session["user_id"])
    user_stocks = db.execute(
        "SELECT symbol, SUM(shares) as total_shares FROM transactions WHERE user_id = :user_id GROUP BY symbol HAVING total_shares > 0", user_id=session["user_id"])

    # add symbol of stock and its corresponding shares to a dictionary
    quotes = {}
    for stock in user_stocks:
        quotes[stock["symbol"]] = lookup(stock["symbol"])

    # remaining cash
    cash_remaining = user[0]["cash"]

    return render_template("index.html", quotes=quotes, stocks=user_stocks, total=cash_remaining, cash_remaining=cash_remaining)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    # user reached route via post
    if request.method == "POST":
        quote = lookup(request.form.get("symbol"))

        # check for a valid symbol
        if quote == None:
            return apology("invalid symbol", 400)

        # check if shares are positive
        try:
            shares = int(request.form.get("shares"))
        except:
            return apology("shares must be a positive integer")

        # check if shares input is positive
        if shares <= 0:
            return apology("shares must be a positive integer")

        # Get data about the user from the database
        data_set = db.execute("SELECT cash FROM users WHERE id = :user_id", user_id=session["user_id"])

        # How much money the user still has in the account
        cash_remaining = data_set[0]["cash"]
        price_per_share = quote["price"]

        # Total price
        total_amount = price_per_share * shares

        # Not enough money
        if cash_remaining < total_amount:
            return apology("Not enough funds")

        # update user data and transaction history
        db.execute("UPDATE users SET cash = cash - :price WHERE id = :user_id", price=total_amount, user_id=session["user_id"])
        db.execute("INSERT INTO transactions (user_id, symbol, shares, price_per_share) VALUES(:user_id, :symbol, :shares, :price)",
                   user_id=session["user_id"],
                   symbol=request.form.get("symbol"),
                   shares=shares,
                   price=price_per_share)

        # send confirmation
        flash("Successfully bought the shares!")

        # redirect
        return redirect(url_for("index"))

    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""

    # get transaction history
    history = db.execute("SELECT symbol, shares, price_per_share, FROM transactions WHERE user_id = :user_id", user_id=session["user_id"])

    return render_template("history.html", history=history)


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
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

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

    # user reached route via post
    if request.method == "POST":

        # lookup for the symbol
        symbol = request.form.get("symbol")
        quote = lookup(symbol)

        # Check for invalid symbols
        if quote == None:
            return apology("invalid input", 400)

        # render the quotation the user asked
        return render_template("quoted.html", quote=quote)

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    # user reached route via post
    if request.method == "POST":

        # Ensure username is submitted
        if not request.form.get("username"):
            return apology("username required!", 400)

        # Ensure password is submitted
        elif not request.form.get("password"):
            return apology("password required!", 400)

        # Ensure passwords match
        elif not request.form.get("password") == request.form.get("confirmation"):
            return apology("passwords don't match", 400)

        # insert new user to the database
        hashed_password = generate_password_hash(request.form.get("password"))
        new_user = db.execute("INSERT INTO users (username, hash) VALUES(:username, :hash)",
                                 username=request.form.get("username"),
                                 hash=hashed_password)

        # Ensure no duplication of usernames
        if not new_user:
            return apology("username already taken, please try a different one", 400)

        # log user in
        # rows = db.execute("SELECT * FROM users WHERE username = :username", username=request.form.get("username"))
        session["user_id"] = new_user

        # notify for successful registration
        flash('Successfully registered!')

        # redirect user to home page
        return redirect(url_for("index"))

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

    if request.method == "POST":
        quote = lookup(request.form.get("symbol"))

        # Check if the symbol exists
        if quote == None:
            return apology("invalid symbol", 400)

        # Check if shares is a positive integer
        try:
            shares = int(request.form.get("shares"))
        except:
            return apology("shares must be a positive integer", 400)

        # Check if shares inputted was less than 0
        if shares <= 0:
            return apology("can't sell less than or 0 shares", 400)

        # Check if we have enough shares
        stock = db.execute("SELECT SUM(shares) as total_shares FROM transactions WHERE user_id = :user_id AND symbol = :symbol GROUP BY symbol",
                           user_id=session["user_id"], symbol=request.form.get("symbol"))

        # Check if user owns shares for the given symbol
        if len(stock) != 1 or stock[0]["total_shares"] <= 0:
            return apology("you don't own shares for this symbol", 400)

        # Check if user has enough shares to sell
        elif stock[0]["total_shares"] < shares:
            return apology("you don't have enough shares to sell", 400)

        # Query database for username
        user_data = db.execute("SELECT cash FROM users WHERE id = :user_id", user_id=session["user_id"])

        # How much money the user has in the account
        cash_remaining = user_data[0]["cash"]
        price_per_share = quote["price"]

        # Calculate the total price of the shares
        total_price = price_per_share * shares

        # Update transaction history
        db.execute("UPDATE users SET cash = cash + :price WHERE id = :user_id", price=total_price, user_id=session["user_id"])
        db.execute("INSERT INTO transactions (user_id, symbol, shares, price_per_share) VALUES(:user_id, :symbol, :shares, :price)",
                   user_id=session["user_id"],
                   symbol=request.form.get("symbol"),
                   shares=-shares,
                   price=price_per_share)

        # notify for a successful transaction
        flash("Shares successfully sold!")

        return redirect(url_for("index"))

    else:
        current_stocks = db.execute(
            "SELECT symbol, SUM(shares) as total_shares FROM transactions WHERE user_id = :user_id GROUP BY symbol HAVING total_shares > 0", user_id=session["user_id"])

        return render_template("sell.html", stocks=current_stocks)

def errorhandler(e):
    """Handle error"""
    return apology(e.name, e.code)


# listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
