# Smart Expense

A simple expense tracker web app with AI-style features, built with Flask and SQLite.

## Features

- **Add expenses** with description, amount and date
- **Automatic categorization** (Food, Shopping, Transport, Bills, Healthcare, Entertainment, Education)
- **Live category preview** while typing the description
- **Unusual expense detection** (an amount more than 2.5x the category average is flagged)
- **Expert system advice** using IF-THEN rules and forward chaining, with a "how did the system decide?" trace
- **Dashboard** with total spending, category totals, a doughnut chart and spending insights

## AI Techniques Used

| Technique | Where it is used |
|---|---|
| Knowledge representation | Category keywords and advice rules (`CATEGORY_KEYWORDS`, `RULES`, `ADVICE` in `app.py`) |
| Forward chaining (expert system) | `build_facts()` and `forward_chain()` produce spending advice from rules |

## Tech Stack

- Python, Flask
- SQLite
- HTML, CSS, Bootstrap 5, Chart.js

## Project Structure

```
SmartExpense/
├── app.py
├── requirements.txt
├── templates/
│   ├── index.html
│   ├── add_expense.html
│   └── dashboard.html
└── static/
    └── style.css
```

`expense.db` is created automatically the first time the app runs.

## How to Run

```bash
# 1. (optional) create and activate a virtual environment
python -m venv .venv
.venv\Scripts\Activate.ps1        # Windows PowerShell
# source .venv/bin/activate       # macOS / Linux

# 2. install dependencies
pip install -r requirements.txt

# 3. start the app
python app.py
```

Then open http://127.0.0.1:5000 in your browser.

## Quick Demo

1. Add `bought shirt` for 500, 800, 700 and 600 (category: Shopping).
2. Add `bought shoes` for 8000 to trigger the unusual expense warning and expert system advice.
3. Add `petrol for bike` (category: Transport).
4. Open the Dashboard and expand "How did the system decide?" to see the rules that fired.
