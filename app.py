from flask import (
    Flask, render_template, request, redirect, url_for, flash, jsonify
)
import sqlite3
import re
from difflib import get_close_matches
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = "smart-expense-secret-key"
DB_NAME = "expense.db"


# ---------------------------------------------------------------
# DATABASE
# ---------------------------------------------------------------
def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS expenses (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            description TEXT    NOT NULL,
            amount      REAL    NOT NULL,
            date        TEXT    NOT NULL,
            category    TEXT    NOT NULL,
            unusual     INTEGER DEFAULT 0
        )
        """
    )
    conn.commit()
    conn.close()


# ===============================================================
# AI TECHNIQUE: KNOWLEDGE REPRESENTATION  (Syllabus Unit IV)
# The category keywords below are the domain knowledge of the system.
# ===============================================================
CATEGORY_KEYWORDS = {
    "Food": [
        "lunch", "dinner", "breakfast", "restaurant", "kfc", "mcdonald",
        "pizza", "burger", "biryani", "cafe", "coffee", "tea", "snack",
        "swiggy", "zomato", "grocery", "groceries", "vegetable", "fruit",
        "hotel", "food", "juice", "bakery", "milk",
    ],
    "Shopping": [
        "shirt", "tshirt", "t-shirt", "jeans", "shoes", "amazon", "flipkart",
        "myntra", "dress", "bag", "watch", "mall", "shopping", "clothes",
        "gift", "headphone", "mobile", "laptop",
    ],
    "Transport": [
        "petrol", "diesel", "fuel", "bus", "train", "metro", "taxi", "uber",
        "ola", "auto", "cab", "ticket", "flight", "bike", "parking", "toll",
    ],
    "Bills": [
        "electricity", "bill", "water", "rent", "recharge", "wifi",
        "internet", "broadband", "gas", "insurance", "emi", "subscription",
        "netflix", "phone bill",
    ],
    "Healthcare": [
        "medicine", "doctor", "hospital", "clinic", "pharmacy", "medical",
        "tablet", "dental", "checkup", "health", "lab test", "scan",
    ],
    "Entertainment": [
        "movie", "cinema", "game", "concert", "party", "pub", "outing",
        "trip", "show",
    ],
    "Education": [
        "book", "books", "course", "fees", "fee", "tuition", "exam",
        "stationery", "pen", "notebook", "college",
    ],
}


# ===============================================================
# AI TECHNIQUE: SPELL CHECKING  (Syllabus Unit V - NLP)
# Corrects typos in the description using the system vocabulary
# (closest word by similarity) before the category is predicted.
# ===============================================================
ALL_WORDS = {
    w for kws in CATEGORY_KEYWORDS.values() for kw in kws for w in kw.split()
}
VOCABULARY = sorted(w for w in ALL_WORDS if len(w) >= 4)


def spell_check(description):
    """Return (corrected_text, [(wrong_word, corrected_word), ...])."""
    corrected_words = []
    corrections = []
    for word in re.findall(r"[a-z0-9\-']+", description.lower()):
        if word.isalpha() and len(word) >= 4 and word not in ALL_WORDS:
            match = get_close_matches(word, VOCABULARY, n=1, cutoff=0.8)
            if match:
                corrections.append((word, match[0]))
                word = match[0]
        corrected_words.append(word)
    return " ".join(corrected_words), corrections


# ---------------------------------------------------------------
# AUTOMATIC CATEGORIZATION (keyword scoring on the corrected text)
# ---------------------------------------------------------------
def predict_category(text):
    text = text.lower()
    best_category = "Other"
    best_score = 0
    for category, keywords in CATEGORY_KEYWORDS.items():
        score = sum(
            1
            for kw in keywords
            if re.search(r"\b" + re.escape(kw) + r"\b", text)
        )
        if score > best_score:
            best_score = score
            best_category = category
    return best_category


# ---------------------------------------------------------------
# UNUSUAL EXPENSE DETECTION
# ---------------------------------------------------------------
def is_unusual(category, amount):
    """An expense is unusual if it is more than 2.5x the average of
    previous expenses in the same category (needs at least 3 records)."""
    conn = get_db()
    rows = conn.execute(
        "SELECT amount FROM expenses WHERE category = ?", (category,)
    ).fetchall()
    conn.close()

    if len(rows) < 3:
        return False
    average = sum(r["amount"] for r in rows) / len(rows)
    return amount > 2.5 * average


# ===============================================================
# AI TECHNIQUE: EXPERT SYSTEM  (Syllabus Unit V)
#   - Knowledge base : RULES + ADVICE (IF-THEN rules)
#   - Working memory : facts derived from the user's expenses
#   - Inference engine: FORWARD CHAINING (Syllabus Unit III)
#   - Explanation    : the list of rules that fired
# ===============================================================
MIN_RECORDS = 3  # minimum expenses needed before the rules are applied

# Each rule is a propositional Horn clause:  p1 AND p2 AND ... THEN q
RULES = [
    {"id": "R1",  "if": ["low_data"],                              "then": "advice_low_data"},
    {"id": "R2",  "if": ["balanced"],                              "then": "advice_balanced"},
    {"id": "R3",  "if": ["enough_data", "food_high"],              "then": "overspending_food"},
    {"id": "R4",  "if": ["enough_data", "shopping_high"],          "then": "overspending_shopping"},
    {"id": "R5",  "if": ["enough_data", "transport_high"],         "then": "overspending_transport"},
    {"id": "R6",  "if": ["enough_data", "entertainment_high"],     "then": "overspending_entertainment"},
    {"id": "R7",  "if": ["overspending_food"],                     "then": "advice_food"},
    {"id": "R8",  "if": ["overspending_shopping"],                 "then": "advice_shopping"},
    {"id": "R9",  "if": ["overspending_transport"],                "then": "advice_transport"},
    {"id": "R10", "if": ["overspending_entertainment"],            "then": "advice_entertainment"},
    {"id": "R11", "if": ["overspending_shopping", "unusual_present"], "then": "impulse_buying"},
    {"id": "R12", "if": ["impulse_buying"],                        "then": "advice_impulse"},
    {"id": "R13", "if": ["unusual_present"],                       "then": "advice_unusual"},
    {"id": "R14", "if": ["spending_rising"],                       "then": "advice_rising"},
    {"id": "R15", "if": ["spending_rising", "unusual_present"],    "then": "budget_risk"},
    {"id": "R16", "if": ["budget_risk"],                           "then": "advice_budget"},
]

# Conclusions that are shown to the user: symbol -> (alert colour, message)
ADVICE = {
    "advice_low_data": (
        "info",
        "Add at least {min_records} expenses so the expert system can "
        "analyse your spending pattern.",
    ),
    "advice_balanced": (
        "success",
        "Your spending looks balanced. No rule found a problem. Keep it up!",
    ),
    "advice_food": (
        "warning",
        "Food is {food_pct:.0f}% of your spending. Try cooking at home or "
        "planning weekly groceries.",
    ),
    "advice_shopping": (
        "warning",
        "Shopping is {shopping_pct:.0f}% of your spending. Compare prices and "
        "avoid unplanned purchases.",
    ),
    "advice_transport": (
        "warning",
        "Transport is {transport_pct:.0f}% of your spending. Consider "
        "carpooling or public transport.",
    ),
    "advice_entertainment": (
        "warning",
        "Entertainment is {entertainment_pct:.0f}% of your spending. Set a "
        "monthly limit for outings.",
    ),
    "advice_impulse": (
        "danger",
        "Possible impulse buying: heavy shopping spend together with an "
        "unusual purchase. Try the 24-hour rule before big purchases.",
    ),
    "advice_unusual": (
        "warning",
        "You have {unusual_count} unusual expense(s). Please review them in "
        "the table below.",
    ),
    "advice_rising": (
        "warning",
        "This month's spending (Rs. {this_month:,.0f}) is {rise_pct:.0f}% "
        "higher than last month (Rs. {last_month:,.0f}).",
    ),
    "advice_budget": (
        "danger",
        "High budget risk: spending is rising and unusual expenses were "
        "found. Set a monthly spending limit.",
    ),
}


def build_facts(expenses):
    """Turn the stored expenses into the initial facts (working memory)."""
    count = len(expenses)
    total = sum(e["amount"] for e in expenses)

    by_category = {}
    for e in expenses:
        by_category[e["category"]] = by_category.get(e["category"], 0) + e["amount"]

    def pct(category):
        return by_category.get(category, 0) / total * 100 if total else 0

    now = datetime.now()
    this_key = now.strftime("%Y-%m")
    prev_key = (now.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
    this_month = sum(e["amount"] for e in expenses if e["date"][:7] == this_key)
    last_month = sum(e["amount"] for e in expenses if e["date"][:7] == prev_key)
    rise_pct = (this_month - last_month) / last_month * 100 if last_month else 0
    unusual_count = sum(1 for e in expenses if e["unusual"])

    stats = {
        "min_records": MIN_RECORDS,
        "food_pct": pct("Food"),
        "shopping_pct": pct("Shopping"),
        "transport_pct": pct("Transport"),
        "entertainment_pct": pct("Entertainment"),
        "this_month": this_month,
        "last_month": last_month,
        "rise_pct": rise_pct,
        "unusual_count": unusual_count,
    }

    facts = set()
    facts.add("enough_data" if count >= MIN_RECORDS else "low_data")
    if stats["food_pct"] > 35:
        facts.add("food_high")
    if stats["shopping_pct"] > 35:
        facts.add("shopping_high")
    if stats["transport_pct"] > 25:
        facts.add("transport_high")
    if stats["entertainment_pct"] > 20:
        facts.add("entertainment_high")
    if unusual_count > 0:
        facts.add("unusual_present")
    if last_month > 0 and rise_pct > 20:
        facts.add("spending_rising")

    problem_facts = {
        "food_high", "shopping_high", "transport_high",
        "entertainment_high", "unusual_present", "spending_rising",
    }
    if "enough_data" in facts and not (facts & problem_facts):
        facts.add("balanced")

    return facts, stats


def forward_chain(initial_facts):
    """Forward chaining: keep firing rules whose conditions are all known
    facts, adding their conclusions as new facts, until nothing changes."""
    facts = set(initial_facts)
    fired = []
    changed = True
    while changed:
        changed = False
        for rule in RULES:
            if rule["then"] not in facts and all(p in facts for p in rule["if"]):
                facts.add(rule["then"])
                fired.append(rule)
                changed = True
    return facts, fired


# ---------------------------------------------------------------
# ROUTES
# ---------------------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/add", methods=["GET", "POST"])
def add_expense():
    if request.method == "POST":
        description = request.form.get("description", "").strip()
        amount_text = request.form.get("amount", "").strip()
        date = request.form.get("date", "").strip()

        if not description or not amount_text or not date:
            flash("Please fill in all fields.", "danger")
            return redirect(url_for("add_expense"))

        try:
            amount = float(amount_text)
            if amount <= 0:
                raise ValueError
        except ValueError:
            flash("Please enter a valid amount greater than 0.", "danger")
            return redirect(url_for("add_expense"))

        corrected_text, corrections = spell_check(description)
        category = predict_category(corrected_text)
        unusual = is_unusual(category, amount)

        conn = get_db()
        conn.execute(
            "INSERT INTO expenses (description, amount, date, category, unusual) "
            "VALUES (?, ?, ?, ?, ?)",
            (description, amount, date, category, 1 if unusual else 0),
        )
        conn.commit()
        conn.close()

        if corrections:
            fixes = ", ".join(f"'{w}' -> '{r}'" for w, r in corrections)
            flash(f"Spell check: {fixes}", "info")
        flash(
            f"Expense added! AI Category: {category} (Rs. {amount:,.0f})",
            "success",
        )
        if unusual:
            flash(
                f"Unusual Expense Detected: Rs. {amount:,.0f} is much higher "
                f"than your usual {category} spending.",
                "warning",
            )
        return redirect(url_for("dashboard"))

    today = datetime.now().strftime("%Y-%m-%d")
    return render_template("add_expense.html", today=today)


@app.route("/spellcheck")
def spellcheck():
    """Used by the Add Expense page to show a live spell-check preview."""
    text = request.args.get("text", "").strip()
    if not text:
        return jsonify({"corrected": "", "corrections": [], "category": ""})
    corrected, corrections = spell_check(text)
    return jsonify(
        {
            "corrected": corrected,
            "corrections": [{"wrong": w, "right": r} for w, r in corrections],
            "category": predict_category(corrected),
        }
    )


@app.route("/dashboard")
def dashboard():
    conn = get_db()

    expenses = conn.execute(
        "SELECT * FROM expenses ORDER BY date DESC, id DESC"
    ).fetchall()

    total = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) AS t FROM expenses"
    ).fetchone()["t"]

    category_rows = conn.execute(
        "SELECT category, SUM(amount) AS total FROM expenses "
        "GROUP BY category ORDER BY total DESC"
    ).fetchall()

    this_month = datetime.now().strftime("%Y-%m")
    month_rows = conn.execute(
        "SELECT category, SUM(amount) AS total FROM expenses "
        "WHERE substr(date, 1, 7) = ? GROUP BY category ORDER BY total DESC",
        (this_month,),
    ).fetchall()
    conn.close()

    categories = [r["category"] for r in category_rows]
    amounts = [r["total"] for r in category_rows]
    category_view = [
        {
            "category": r["category"],
            "total": r["total"],
            "percent": (r["total"] / total * 100) if total else 0,
        }
        for r in category_rows
    ]

    # ---- SPENDING INSIGHTS ----
    insights = []
    if category_rows:
        top = category_rows[0]
        percent = top["total"] / total * 100
        insights.append(
            f"Your highest spending category is {top['category']} "
            f"(Rs. {top['total']:,.0f}, {percent:.0f}% of total spending)."
        )
    if month_rows:
        top_month = month_rows[0]
        insights.append(
            f"This month you spent the most on {top_month['category']}: "
            f"Rs. {top_month['total']:,.0f}."
        )
        for row in month_rows:
            if row["category"] == "Food":
                insights.append(
                    f"You spent Rs. {row['total']:,.0f} on Food this month."
                )
    unusual_count = sum(1 for e in expenses if e["unusual"])
    if unusual_count:
        insights.append(
            f"{unusual_count} unusual expense(s) detected. Review them below."
        )
    if not insights:
        insights.append("Add some expenses to see AI insights here.")

    # ---- EXPERT SYSTEM (forward chaining) ----
    initial_facts, stats = build_facts(expenses)
    _, fired_rules = forward_chain(initial_facts)

    advice = [
        {
            "level": ADVICE[r["then"]][0],
            "text": ADVICE[r["then"]][1].format(**stats),
        }
        for r in fired_rules
        if r["then"] in ADVICE
    ]
    trace = [
        {
            "id": r["id"],
            "text": "IF " + " AND ".join(r["if"]) + " THEN " + r["then"],
        }
        for r in fired_rules
    ]

    # Spell-check note for each expense (shown under the description)
    expenses_view = []
    for e in expenses:
        item = dict(e)
        _, fixes = spell_check(e["description"])
        item["fixes"] = fixes
        expenses_view.append(item)

    return render_template(
        "dashboard.html",
        expenses=expenses_view,
        total=total,
        expense_count=len(expenses),
        top_category=category_rows[0]["category"] if category_rows else "-",
        unusual_count=unusual_count,
        category_rows=category_view,
        categories=categories,
        amounts=amounts,
        insights=insights,
        advice=advice,
        known_facts=sorted(initial_facts),
        trace=trace,
    )


@app.route("/delete/<int:expense_id>", methods=["POST"])
def delete_expense(expense_id):
    conn = get_db()
    conn.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
    conn.commit()
    conn.close()
    flash("Expense deleted.", "info")
    return redirect(url_for("dashboard"))


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
