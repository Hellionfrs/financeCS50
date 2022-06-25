import os
import datetime

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")
cv = db.execute("CREATE TABLE IF NOT EXISTS stocks(user_id INTEGER NOT NULL,comp_symbol TEXT NOT NULL,comp_name TEXT NOT NULL,t_shares INTEGER NOT NULL, stock_price INTEGER NOT NULL, sub_total INTEGER NOT NULL, FOREIGN KEY(user_id) REFERENCES users(id))")
ca = db.execute("CREATE TABLE IF NOT EXISTS history(owner_id INTEGER NOT NULL, symbol TEXT NOT NULL, shares INTEGER NOT NULL, price INTEGER NOT NULL, date TEXT NOT NULL, FOREIGN KEY(owner_id) REFERENCES users(id))")
# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Completed!


@app.route("/", methods=["GET", "POST"])
@login_required
def index():
    """Show portfolio of stocks"""
    try:
        # get info from table stocks that will display on "/"
        user_info = db.execute("SELECT * FROM stocks WHERE user_id=? and t_shares > 0 ORDER BY comp_symbol ASC", session["user_id"])
        # cash that the user have
        user_cash = db.execute("SELECT * FROM users WHERE id=?", session["user_id"])
        user_subtotal = db.execute("SELECT SUM(sub_total) from stocks WHERE user_id=?",session["user_id"])
        user_total = user_cash[0]["cash"] + user_subtotal[0]["SUM(sub_total)"]
        return render_template("index.html", users=user_info, cash=usd(user_cash[0]["cash"]), total=usd(user_total))
    except:

        user_cash = db.execute("SELECT * FROM users WHERE id=?", session["user_id"])
        return render_template("index.html", cash=usd(user_cash[0]["cash"]), total=usd(user_cash[0]["cash"]))

# Completed!


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        input = request.form.get("shares")
        if not request.form.get("symbol"):
            return (apology("missing symbol", 400))
        elif not request.form.get("shares"):
            return (apology("missing shares"))
        elif lookup(request.form.get("symbol")) == None:
            return (apology("invalid symbol", 400))
        elif input.isalpha() == True:
            return (apology("shares must be numbers!"))
        elif (float(request.form.get("shares")) < 0):
            return (apology("shares must be positive!"))
        elif float(input).is_integer() == False:
            return (apology("shares must be intergers!"))

        else:
            # Get data via request.form
            dictionary = lookup(request.form.get("symbol"))
            cant = float(request.form.get("shares"))
            # Get data from dictionary from lookup()
            companyPrice = float(dictionary["price"])
            companySymbol = dictionary["symbol"]
            companyName = dictionary["name"]

            total = db.execute("SELECT * FROM users WHERE id = ?", session["user_id"])
            total_cash = total[0]["cash"]
            # save buy info in stocks session["user_id"]
            # check if there is already a stock on stocks
            if total_cash < (cant*companyPrice):
                return (apology("cannot affort the purchase"))
            else:

                row = db.execute("SELECT * FROM stocks WHERE user_id= ? and comp_name= ?", session["user_id"], companyName)
                try:
                    if row[0]["comp_name"] is not None:
                        # current stocks
                        stocks_now = float(row[0]["t_shares"]) + cant
                        # update info on stocks and in history
                        # stocks
                        db.execute("UPDATE stocks SET t_shares=?, sub_total=? WHERE user_id=? and comp_name = ?",
                                    stocks_now, stocks_now*companyPrice, session["user_id"], companyName)
                        # history add transaction
                        db.execute("INSERT INTO history (owner_id,symbol,shares,price,date) VALUES(?,?,?,?,?)",
                                    session["user_id"], companySymbol, cant, companyPrice, datetime.datetime.now())
                        db.execute("UPDATE users SET cash=? WHERE id=?", (total_cash) - (companyPrice * cant), session["user_id"])
                        flash("Bought!")
                # If theres is not already a stock insert into stocks and history tables
                except:
                    db.execute("INSERT INTO stocks (user_id,comp_symbol,comp_name,t_shares,stock_price,sub_total) VALUES(?,?,?,?,?,?)",
                                session["user_id"], companySymbol, companyName, cant, companyPrice, cant*companyPrice)
                    db.execute("INSERT INTO history (owner_id,symbol,shares,price,date) VALUES(?,?,?,?,?)",
                                session["user_id"], companySymbol, cant, companyPrice, datetime.datetime.now())
                    #save purcharse history
                    db.execute("UPDATE users SET cash=? WHERE id=?", (total_cash) - (companyPrice * cant), session["user_id"])
                    flash("Bought!")
            return redirect("/")

    return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    try:
        user_info = db.execute("SELECT symbol, price, shares, date FROM history  WHERE owner_id=?", session["user_id"])
        return render_template("history.html", users=user_info)
    except:
        return render_template("history.html")


@app.route("/cash", methods=["GET", "POST"])
@login_required
def cash():
    """Get more Cash"""
    if request.method == "POST":
        input = request.form.get("cash")
        if not input:
            return (apology("missing cash", 400))
        elif input.isalpha() == True:
            return (apology("cash must be numbers!"))
        elif (float(request.form.get("cash")) < 0):
            return (apology("cash must be positive!"))
        else:
            user_info = db.execute("SELECT * FROM users WHERE id = ?", session["user_id"])
            current_cash = user_info[0]["cash"]
            db.execute("UPDATE users SET cash=? WHERE id=?", current_cash + float(input), session["user_id"])
            flash("Got more Cash!")
            return redirect("/")
    else:
        return render_template("cash.html")


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

# Completed!


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""

    if request.method == "POST":
        if not request.form.get("symbol"):
            return (apology("missing symbol", 400))
        elif lookup(request.form.get("symbol")) == None:
            return (apology("invalid symbol", 400))
        else:
            dictionary = lookup(request.form.get("symbol"))
            companyName = dictionary["name"]
            companyPrice = dictionary["price"]
            companySymbol = dictionary["symbol"]
            return render_template("quoted.html", name=companyName, price=usd(companyPrice), symbol=companySymbol)

    return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":
        usrname = request.form.get("username")
        usrhash = generate_password_hash(request.form.get("password"))
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))
        # Checks if user provides a user name in the form
        if not usrname:
            return apology("must provide username", 400)
        elif not request.form.get("password"):
            return apology("must provide password", 400)
        elif not request.form.get("confirmation"):
            return apology("must provide confirmation password", 400)
        elif request.form.get("password") != request.form.get("confirmation"):
            return apology("passwords should match!", 400)
        # Check if user name already exist
        try:
            if rows[0]["username"] != None:
                return apology("username already used", 400)

        except:
            db.execute("INSERT INTO users (username,hash) VALUES(?,?)", usrname, usrhash)
            flash("Registered!")
            return redirect("/")
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "POST":
        # inputs
        input_symbol = request.form.get("symbol")
        input_sell_shares = int(request.form.get("shares"))
        # return (input_sell_shares)
        # checks
        if not request.form.get("symbol"):
            return (apology("missing symbol", 400))
        elif not request.form.get("shares"):
            return (apology("missing shares", 400))
        else:
            #get list of symbols that the user already have from stocks table
            list_symbols = db.execute(
                "SELECT comp_symbol FROM stocks WHERE user_id=? and t_shares > 0 ORDER BY comp_symbol ASC", session["user_id"])
            # if user doesnt have any stock bough it still return the template empty
            if list_symbols[0]["comp_symbol"] is None:
                return render_template("sell.html")
            # row of user stocks(symbol)
            else:
                # get info how many stocks the user have
                row = db.execute("SELECT * FROM stocks WHERE user_id=? and comp_symbol=?", session["user_id"], input_symbol)
                stocks = row[0]["t_shares"]

                def check_if(sample_dict, value):
                    """Check if given value exists in list of dictionaries """
                    for elem in sample_dict:
                        if value in elem.values():
                            return True
                    return False
                # if user doesnt have stocks returns a apology template
                if stocks is None:
                    return (apology("need more shares!", 400))
                # check if input_sell_shares < stocks the user have (stocks) returns a apology template
                elif input_sell_shares > stocks:
                    return (apology("not enough stocks :(", 400))
                # checks if input_symbol provided by user actually exist on the options we provided

                elif check_if(list_symbols, input_symbol) == False:
                    return (apology("stocks not found", 400))
                elif (input_sell_shares < 0):
                    return (apology("shares must be positive", 400))
                else:
                    dictionary = lookup(request.form.get("symbol"))
                    companyPrice = float(dictionary["price"])
                    # data from users $$
                    total = db.execute("SELECT * FROM users WHERE id = ?", session["user_id"])
                    total_cash = total[0]["cash"]
                    # update stocks table
                    stocks_now = stocks - input_sell_shares
                    db.execute("UPDATE stocks SET t_shares=?, sub_total=? WHERE user_id=? and comp_symbol=?",
                                stocks_now, stocks_now*companyPrice, session["user_id"], input_symbol)
                    # update history table
                    db.execute("INSERT INTO history (owner_id,symbol,shares,price,date) VALUES(?,?,?,?,?)",
                                session["user_id"], input_symbol, (input_sell_shares)*(-1), companyPrice, datetime.datetime.now())
                    db.execute("UPDATE users SET cash=? WHERE id=?", total_cash +
                                (companyPrice*input_sell_shares), session["user_id"])
                    flash("Sold!")
                return redirect("/")

    else:
        try:
            symbols = db.execute(
                "SELECT * FROM stocks WHERE user_id=? and t_shares > 0 ORDER BY comp_symbol ASC", session["user_id"])
            return render_template("sell.html", symbols=symbols)
        except:
            return render_template("sell.html")

