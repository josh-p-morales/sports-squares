# 🏀 College Basketball Sports Squares (ESPN -> Google Sheets)

A Python application that gathers college basketball scores by period (1st Half, 2nd Half, Quarters, Overtime, and Final) directly from **ESPN** (free public API, **no API key required**) and injects them into a Google Sheet. It automatically calculates winning digits for **Sports Squares pools** (`Away Last Digit` and `Home Last Digit`) exclusively for **Final scores**.

---

## ✨ Features

- **Free Public ESPN Data (No API Key Required)**:
  - Powered by ESPN's official public college basketball scoreboard API.
  - Supports **NCAA Division I Men's Basketball** (two 20-minute halves).
  - Supports **NCAA Division I Women's Basketball** (four 10-minute quarters).
  - Full Overtime (OT) tracking and live in-game clock status.
  - Zero registration, zero rate limit fees, and zero credit cards.
- **March Madness Tournament Filter (By Year & Round)**:
  - Query **entire NCAA Tournaments** for any given year with `--year <YYYY>` (fetches all ~67 tournament games across all rounds in seconds).
  - Automatically isolates March Madness tournament games (`groups=100`) from NIT, CBI, and regular season games.
  - Extracted tournament rounds and regions (e.g. `1st Round`, `Sweet 16`, `Elite 8`, `Final Four`, `National Championship`).
  - Filter by specific rounds with `--round "<Round Name>"`.
- **Final Scores & Squares Calculation**:
  - Automatically filters and syncs only completed games (`Final`).
  - Computes winning squares digit combinations (`Away % 10` and `Home % 10`) for **Final** scores.
- **Four Google Sheets Views**:
  - **`Game Board`**: A 10x10 squares pool board with unique random digits (0-9) for HOME TEAM and AWAY TEAM, solid black corner, alternating row shading, and cell borders.
  - **`Payouts`**: Dedicated payouts dashboard with room for 100 unique players automatically populated from the Game Board, square counts, cell coordinates, round-by-round winnings, and bold total payouts.
  - **`Games Log`**: Tabular records of completed games, period scores, round/region, statuses, final winning squares, and winning cell coordinates with in-place upserting.
  - **`Squares Tracker`**: Event log of Final winning squares keys (e.g. `Away 7 - Home 6 [A7-H6]`), winning cell coordinate, and winning player lookup (`Winner (Player)`).
- **Flexible Execution**:
  - Run as a **single-shot fetch** (for scheduled cron jobs or on-demand runs).
  - Run as a **live polling service** (continuously checking live scores every `N` seconds with live terminal summary).
  - Local **`--mock`** and **`--dry-run`** modes for instant offline testing and development.
- **Diagnostic Utilities**:
  - Built-in `test` command to verify ESPN connection and Google Sheets permissions.
  - Built-in `setup-guide` command displaying 1-minute zero-cloud Google Apps Script instructions.

---

## 🚀 Quick Start Guide

### 1. Prerequisites & Virtual Environment

Ensure you have Python 3.10+ installed. A virtual environment has already been set up in `.venv/`. If setting up anew:

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Credentials (`.env`)

Copy `.env.example` to `.env`:

```powershell
cp .env.example .env
```

Open `.env` and fill in your values:

```ini
# Data Source (ESPN is default and free; no API key needed)
DATA_SOURCE=espn
ESPN_LEAGUE=mens       # "mens" (NCAA Men's Basketball) or "womens" (NCAA Women's Basketball)

# Google Sheets Access (OPTION A - Recommended: Zero Google Cloud setup)
GOOGLE_WEBHOOK_URL=https://script.google.com/macros/s/YOUR_APPS_SCRIPT_ID/exec

# Polling Interval (in seconds) when running in live poll mode
POLL_INTERVAL_SECONDS=60
```

---

## ⚡ Zero-Cloud Setup: Google Sheets via Apps Script Webhook (1 Minute)

You do **NOT** need Google Cloud, IAM roles, or JSON keys. You can connect directly using Google Apps Script:

1. Open your Google Spreadsheet in your browser:
   `https://docs.google.com/spreadsheets/d//edit`
2. In the top toolbar, click **Extensions > Apps Script**.
3. Delete any default code in `Code.gs`, and paste the entire contents of [google_apps_script.js](file:///c:/sports_squares/google_apps_script.js).
4. Click the **Save** (disk) icon.
5. In the top right, click **Deploy > New deployment**:
   - Click the gear icon next to *Select type* and choose **Web app**.
   - **Description**: `Sports Squares Sync`
   - **Execute as**: `Me`
   - **Who has access**: `Anyone`
6. Click **Deploy** (Google will prompt for a one-time authorization: click *Advanced* > *Go to (unsafe)* > *Allow*).
7. Copy the **Web app URL** (starts with `https://script.google.com/macros/s/.../exec`).
8. Paste it into your `.env` file:
   ```ini
   GOOGLE_WEBHOOK_URL=https://script.google.com/macros/s/YOUR_URL_HERE/exec
   ```

*(Alternative: If you ever prefer a Google Cloud Service Account, you can still place `service_account.json` in the folder and set `GOOGLE_SERVICE_ACCOUNT_PATH` and `GOOGLE_SPREADSHEET_ID`).*

---

## 🛠️ Usage & Commands

### Test Diagnostics
Check that the ESPN API and your Google Sheets connection are working properly:
```powershell
.venv\Scripts\python main.py test
```

### 1. Fetching March Madness Tournament Games

Sync an entire NCAA Tournament for any year directly to Google Sheets (~67 games):
```powershell
.venv\Scripts\python main.py fetch --year 2024
```

Filter March Madness for a specific round:
```powershell
.venv\Scripts\python main.py fetch --year 2024 --round "Sweet 16"
.venv\Scripts\python main.py fetch --year 2024 --round "Final Four"
.venv\Scripts\python main.py fetch --year 2024 --round "National Championship"
```

Fetch Women's March Madness tournament:
```powershell
.venv\Scripts\python main.py fetch --year 2024 --gender womens
```

Preview March Madness games locally in terminal without updating Google Sheets:
```powershell
.venv\Scripts\python main.py fetch --year 2024 --dry-run
```

### 2. Single Fetch by Date (On-Demand)
Fetch today's games:
```powershell
.venv\Scripts\python main.py fetch
```

Fetch games for a specific calendar date and filter for tournament games only:
```powershell
.venv\Scripts\python main.py fetch --date 2024-03-24 --tournament
```

Fetch only games that are currently live:
```powershell
.venv\Scripts\python main.py fetch --live
```

### 3. Setup or Regenerate Game Board
Create the 10x10 squares grid tab named `game board` with randomized digits (0-9). This also automatically sets up the `Payouts` sheet if one does not already exist:
```powershell
.venv\Scripts\python main.py create-board
```

If the board already exists and you wish to reshuffle and regenerate new numbers:
```powershell
.venv\Scripts\python main.py create-board --force
```

*(Note: You can also click **🏀 Sports Squares > Setup Game Board** directly in Google Sheets).*

### 4. Setup Payouts Sheet
Create or verify the `Payouts` sheet independently:
```powershell
.venv\Scripts\python main.py setup-payouts
```

If you wish to reset or rebuild the `Payouts` sheet:
```powershell
.venv\Scripts\python main.py setup-payouts --force
```

*(Note: You can also click **🏀 Sports Squares > Setup Payouts Sheet** directly in Google Sheets).*

### 5. Live Polling Service
Continuously monitor in-progress tournament games and auto-refresh Google Sheets every 60 seconds (or custom interval):
```powershell
.venv\Scripts\python main.py poll --tournament --interval 60
```

To run polling for women's tournament games:
```powershell
.venv\Scripts\python main.py poll --tournament --gender womens --interval 60
```

### 6. Setup Guide
View the 1-minute Google Apps Script setup instructions anytime in terminal:
```powershell
.venv\Scripts\python main.py setup-guide
```

---

## 📊 Google Sheets Layout

### Tab 1: `Game Board` (10x10 Squares Pool Board)
- **Top Header**: `HOME TEAM` merged across columns `C7:L7`.
- **Top Digits Row**: Row 8 contains digits for the Home Team across columns `C8:L8` (Home 0 = C, 1 = D, ..., 9 = L).
- **Left Header**: `AWAY TEAM` vertically merged along rows `A9:A18` (rotated 90° upward).
- **Left Digits Column**: Column B contains digits for the Away Team down rows `B9:B18` (Away 0 = Row 9, 1 = Row 10, ..., 9 = Row 18).
- **Corner Cell**: Cell `B8` is a solid black marker (`#000000`).
- **Squares Grid**: 10x10 grid on cells `C9:L18` with alternating shading and borders.
- **Payout & Buy-In Schedule**: Displayed on rows 3-4 across columns `D:J` (1st Rnd, 2nd Rnd, Sweet 16, Elite 8, Final 4, Championship, Buy In).

### Tab 2: `Payouts` (100-Player Payout Dashboard)
- **Row 1 Banner**: Merged `A1:J1` titled **"Payouts"** with rich gold fill (`#F6CE47`) and bold 26pt text.
- **Row 2 Column Headers**:
  - `A`: **People playing** (deduplicated, sorted dynamically from `'Game Board'!$C$9:$L$18` via formula `=IFERROR(SORT(UNIQUE(TOCOL('Game Board'!$C$9:$L$18, 1))), "")`).
  - `B`: **# of squares** (formula `=IF(A{r}="", "", COUNTIF('Game Board'!$C$9:$L$18, A{r}))`).
  - `C`: **Board Cells** (inserted column displaying all cells on the Game Board where the player exists, e.g. `C9, L9, C18`).
  - `D - I`: **1st Rnd, 2nd Rnd, Sweet 16, Elite 8, Final 4, FINALS** (round payouts; soft pink `#FCE4D6` background by default, conditional green `#70AD47` highlight when a player wins > $0).
  - `J`: **Total Won** (bold `$#,##0` formatted sum across all rounds).
- **100-Player Capacity**: Rows 3 to 102 are pre-wired with dynamic formulas to accommodate up to 100 unique players as they are added to the Game Board.

### Tab 3: `Games Log`
| Game ID | Date | Time | Round / Region | Status | Away Team | Away 1H | Away 2H | Away Total | Home Team | Home 1H | Home 2H | Home Total | Final Square | Winning Cell | Last Updated |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 401638612 | 2024-03-24 | 18:15 | Midwest Region - 2nd Round | Final | Utah State | 33 | 34 | 67 | Purdue | 49 | 57 | 106 | Away 7 - Home 6 (A7-H6) | I16 | 2024-03-24 20:30 |

### Tab 4: `Squares Tracker`
| Game ID | Matchup | Round / Region | Status | Away Final Score | Home Final Score | Away Digit | Home Digit | Winning Square Key | Winning Cell | Winner (Player) | Last Updated |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 401638612 | Utah State @ Purdue | Midwest Region - 2nd Round | Final | 67 | 106 | 7 | 6 | Away 7 - Home 6 [A7-H6] | I16 | Chip | 2024-03-24 20:30 |


---

## 📁 Project Structure

```
sports_squares/
│── .env.example             # Template for configuration & Webhook URL
│── .gitignore               # Keeps credentials and cache files safe
│── config.py                # Environment variable management
│── main.py                  # CLI entry point (fetch, poll, test, setup-guide)
│── google_apps_script.js    # Google Apps Script webhook for Google Sheets
│── requirements.txt         # Project dependencies
│── README.md                # Documentation & instructions
│── src/
│   ├── espn_client.py       # ESPN College Basketball public API client
│   ├── sheets_client.py     # Google Sheets manager (Games Log & Squares Tracker)
│   ├── parser.py            # Period scoring, round metadata & square digit extractor
│   ├── runner.py            # Execution coordinator & polling loop
│   └── mock_data.py         # Sample data for offline testing
```
