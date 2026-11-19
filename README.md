# ✈️ Travel Expense Tracker AI Agent

An autonomous AI agent designed to log, categorize, and analyze expenses during trips using natural language, receipt photos, and simple commands—providing real-time budget tracking and burn-rate intelligence.

---

## 🌟 Key Features

1. **Natural Language Expense Logging:** Say *"Paid 45 euros for dinner in Rome, split with Sam"* and the agent resolves dates, currencies, categories, and split notes.
2. **UPI & Bank SMS Auto-Parser (Modern FinTech):** Paste raw payment alerts from Google Pay, PhonePe, Paytm, BHIM, or Credit Cards. Auto-extracts amount, vendor, payment mode, and reference ID.
3. **Group Debt Settlement Engine (Splitwise Algorithm):** Calculates "who owes whom" across multi-traveler trips, solves the Minimum Cash Flow debt simplification problem, and generates ready-to-share WhatsApp summaries.
4. **Hands-Free Voice-to-Expense Input:** Tap the microphone button in the dashboard to speak expenses on the go using native Web Speech API.
5. **Real-Time Anomaly & Duplicate Guard:** Automatically detects duplicate swipes (within 24 hrs), suspicious price surges (>2.5x category average), and severe budget drains.
6. **Multimodal Receipt Vision (Google AI Studio / Gemini):** Upload receipt photos and `gemini-3.8-flash` extracts merchant, date, amount, currency, and line items.
7. **Zero-Hallucination & Clarifying Guardrails:** The agent asks a clarifying question whenever an amount, currency, or date is ambiguous—never inventing data.
8. **One-Line Confirmations:** Crisp single-sentence confirmations for every logged transaction.
9. **Multi-Currency Support & Local FX Caching:** Automatically converts expenses to your trip's home currency using historical rates from the Frankfurter API, cached locally in SQLite.
10. **Auto-Categorization with Active Learning:** Automatically classifies purchases into `food`, `transport`, `lodging`, `activities`, `shopping`, `fees`, and `other`. When you correct a category, the agent saves a rule and remembers it for future expenses.
11. **Real-Time Budget Analytics:** Tracks daily burn rate, target budget per remaining day, and alerts you before projected overspending happens.
12. **Exportable Reports:** Download your trip expenses as CSV at any time.

---

## 🛠️ Tech Stack

- **Backend:** Python 3.10+ / FastAPI
- **Database:** SQLite (SQLAlchemy 2.0 ORM, easily migratable to PostgreSQL)
- **AI / LLM:** Google Gemini API (`gemini-3.8-flash` via official `google-genai` SDK)
- **Exchange Rates:** Frankfurter API (European Central Bank data) + SQLite local cache
- **Frontend:** Responsive Web Dashboard (HTML5, Vanilla JS, CSS Grid, Chart.js)

---

## 🚀 Quick Start Guide

### 1. Configure Your Google AI Studio API Key
Create a `.env` file in the project root by copying `.env.example`:

**On Windows (PowerShell):**
```powershell
Copy-Item .env.example .env
```

Open `.env` and paste your Google AI Studio API key:
```env
GEMINI_API_KEY=your_actual_gemini_api_key_here
```
*(Note: If you don't have an API key right away, the app includes a built-in deterministic offline parser so you can still run, test, and use the full dashboard!)*

---

### 2. Run the Application
Launch the server using Python:

**Command:**
```powershell
python -m uvicorn app.main:app --reload --port 8000
```
*Or simply:*
```powershell
python app/main.py
```

---

### 3. Open the Web Dashboard
Open your web browser and navigate to:
```text
http://127.0.0.1:8000
```

- **Interactive API Docs:** Available at `http://127.0.0.1:8000/docs`

---

## 💬 Sample Prompts to Try in the Chat

- **Log a foreign expense:**
  > *"Paid 45 euros for dinner in Rome, split with Sam"*
- **Log transport:**
  > *"Spent $32 on an Uber to the hotel yesterday"*
- **Test ambiguity detection:**
  > *"Bought coffee and gelato"*  
  *(Agent will ask: "How much did you pay, in which currency, and was this today?")*
- **Correct a category & teach the agent:**
  > *"Change expense #1 to food, Starbucks is food not shopping"*
- **Ask analytical budget questions:**
  > *"Am I on track for my budget?"*  
  > *"How much did I spend on food in Rome?"*  
  > *"What is my daily burn rate?"*
- **Auto-log from raw UPI / Card SMS:**
  > *"Sent Rs.450.00 from Kotak Bank AC X1234 to STARBUCKS via UPI Ref 412345678901 on 18-11-26"*
- **Ask who owes whom (Splitwise Settlements):**
  > *"Who owes whom in this trip? Show settlements"*
- **Check for duplicate swipes or price surges:**
  > *"Check for any duplicate or unusual expenses"*
- **Voice logging:**
  > Click the **🎙️** mic button and speak naturally: *"Spent 300 rupees on auto to station"*.
- **Upload a receipt:**
  > Drag and drop any receipt picture into the camera box to auto-extract and log it.

---

## 🧪 Running the Automated Tests

The test suite covers currency conversion caching, ambiguity guardrails, zero-hallucination checks, receipt parsing, and budget burn-rate calculations:

```powershell
python -m pytest tests/
```
