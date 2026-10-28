import requests
from typing import List, Dict, Any, Optional
from datetime import datetime
from rich.console import Console
from .parser import GameRecord

console = Console()

GAMES_LOG_HEADERS = [
    "Game ID",
    "Date",
    "Time",
    "Status",
    "Round / Region",
    "Away Team",
    "Away 1H/Q1",
    "Away 2H/Q2",
    "Away Q3",
    "Away Q4",
    "Away OT",
    "Away Total",
    "Home Team",
    "Home 1H/Q1",
    "Home 2H/Q2",
    "Home Q3",
    "Home Q4",
    "Home OT",
    "Home Total",
    "Final Square (Away-Home)",
    "Winning Cell",
    "Last Updated (UTC)",
]

SQUARES_TRACKER_HEADERS = [
    "Game ID",
    "Matchup",
    "Round / Region",
    "Status",
    "Away Final Score",
    "Home Final Score",
    "Away Digit",
    "Home Digit",
    "Winning Square Key",
    "Winning Cell",
    "Winner (Player)",
    "Last Updated (UTC)",
]


def build_squares_rows(games: List[GameRecord], now_utc: str) -> List[List[Any]]:
    """Helper to convert GameRecords into Squares Tracker row data (Final scores only)."""
    col_letters = ["C", "D", "E", "F", "G", "H", "I", "J", "K", "L"]
    rows = []
    for game in games:
        if game.away_total is not None and game.home_total is not None and game.is_finished:
            matchup = f"{game.away_team} @ {game.home_team}"
            t_round = game.tournament_round or ""
            a_dig = game.away_total % 10
            h_dig = game.home_total % 10
            win_cell = f"{col_letters[h_dig]}{9 + a_dig}"
            winner_formula = f'=IFERROR(INDIRECT("\'Game Board\'!{win_cell}"), "")'
            rows.append([
                game.game_id,
                matchup,
                t_round,
                game.status_long or "Final",
                game.away_total,
                game.home_total,
                a_dig,
                h_dig,
                f"Away {a_dig} - Home {h_dig} [A{a_dig}-H{h_dig}]",
                win_cell,
                winner_formula,
                now_utc,
            ])
    return rows


class WebhookSheetsClient:
    """
    Connects to Google Sheets via a Google Apps Script Web App URL.
    Requires ZERO Google Cloud console configuration, zero service accounts, and zero JSON keys.
    """

    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url.strip()

    def test_connection(self) -> Dict[str, Any]:
        """Pings the webhook with a GET request to verify health."""
        try:
            res = requests.get(self.webhook_url, allow_redirects=True, timeout=15)
            if res.status_code == 401 or "accounts.google.com" in res.text or "text/html" in res.headers.get("content-type", ""):
                raise RuntimeError(
                    "Google Apps Script Web App is set to private.\n"
                    "Fix in 15 seconds:\n"
                    "  1. In your Google Sheet, click Extensions > Apps Script\n"
                    "  2. Click 'Deploy' (top right) > 'Manage deployments'\n"
                    "  3. Click the pencil (Edit) icon next to your active deployment\n"
                    "  4. Under 'Who has access', change it from 'Only myself' to 'Anyone'\n"
                    "  5. Click 'Deploy'"
                )
            res.raise_for_status()
            return res.json()
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Failed to reach Google Apps Script Webhook: {e}")
        except Exception as e:
            raise RuntimeError(f"{e}")

    def initialize_sheets(self) -> None:
        """Verifies endpoint is reachable."""
        self.test_connection()

    def sync_all(self, games: List[GameRecord]) -> Dict[str, int]:
        """Sends both Games Log and Squares rows in a single batch POST."""
        if not games:
            return {"games": 0, "squares": 0}

        now_utc = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        game_rows = [g.to_sheet_row(now_utc) for g in games]
        squares_rows = build_squares_rows(games, now_utc)

        payload = {
            "action": "sync",
            "games": game_rows,
            "squares": squares_rows,
        }

        try:
            # Google Apps Script web apps return a 302 redirect to script.googleusercontent.com
            # requests follows this with allow_redirects=True automatically.
            response = requests.post(
                self.webhook_url,
                json=payload,
                allow_redirects=True,
                headers={"Content-Type": "application/json"},
                timeout=30,
            )
            if response.status_code == 401 or "accounts.google.com" in response.text or "text/html" in response.headers.get("content-type", ""):
                raise RuntimeError(
                    "Google Apps Script Web App is set to private.\n"
                    "Fix in 15 seconds:\n"
                    "  1. In your Google Sheet, click Extensions > Apps Script\n"
                    "  2. Click 'Deploy' > 'Manage deployments'\n"
                    "  3. Click the pencil (Edit) icon next to your deployment\n"
                    "  4. Under 'Who has access', change it from 'Only myself' to 'Anyone'\n"
                    "  5. Click 'Deploy'"
                )
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"HTTP error communicating with Google Apps Script: {e}")
        except Exception as e:
            raise RuntimeError(f"{e}")

        if data.get("status") == "error":
            raise RuntimeError(f"Google Apps Script Error: {data.get('message')}")

        return {
            "games": data.get("gamesUpdated", len(game_rows)),
            "squares": data.get("squaresUpdated", len(squares_rows)),
        }

    def sync_games_log(self, games: List[GameRecord]) -> int:
        result = self.sync_all(games)
        return result["games"]

    def sync_squares_tracker(self, games: List[GameRecord]) -> int:
        # Synced in sync_all; return estimate or 0 to avoid double-call if called separately
        return len(build_squares_rows(games, datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")))

    def create_game_board(
        self,
        force: bool = False,
        home_digits: Optional[List[int]] = None,
        away_digits: Optional[List[int]] = None
    ) -> Dict[str, Any]:
        """Requests creation/configuration of the 'game board' tab via Apps Script webhook."""
        import random
        if home_digits is None:
            home_digits = list(range(10))
            random.shuffle(home_digits)
        if away_digits is None:
            away_digits = list(range(10))
            random.shuffle(away_digits)

        payload = {
            "action": "create_board",
            "force": force,
            "homeDigits": home_digits,
            "awayDigits": away_digits,
        }

        try:
            response = requests.post(
                self.webhook_url,
                json=payload,
                allow_redirects=True,
                headers={"Content-Type": "application/json"},
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"HTTP error communicating with Google Apps Script: {e}")
        except Exception as e:
            raise RuntimeError(f"{e}")

        if data.get("status") == "error":
            raise RuntimeError(f"Google Apps Script Error: {data.get('message')}")

        return data.get("boardResult", data)

    def create_payouts_sheet(self, force: bool = False) -> Dict[str, Any]:
        """Requests creation/configuration of the 'Payouts' tab via Apps Script webhook."""
        payload = {
            "action": "create_payouts",
            "force": force,
        }

        try:
            response = requests.post(
                self.webhook_url,
                json=payload,
                allow_redirects=True,
                headers={"Content-Type": "application/json"},
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"HTTP error communicating with Google Apps Script: {e}")
        except Exception as e:
            raise RuntimeError(f"{e}")

        if data.get("status") == "error":
            raise RuntimeError(f"Google Apps Script Error: {data.get('message')}")

        return data.get("payoutsResult", data)


class GoogleSheetsClient:
    """Manages connection, upserts, and formatting using a Google Cloud Service Account."""

    def __init__(
        self,
        service_account_path: str,
        spreadsheet_id: str,
        games_log_title: str = "Games Log",
        squares_tracker_title: str = "Squares Tracker",
    ):
        import gspread
        self.service_account_path = service_account_path
        self.spreadsheet_id = spreadsheet_id
        self.games_log_title = games_log_title
        self.squares_tracker_title = squares_tracker_title

        try:
            self.gc = gspread.service_account(filename=self.service_account_path)
            self.spreadsheet = self.gc.open_by_key(self.spreadsheet_id)
        except gspread.exceptions.SpreadsheetNotFound:
            raise RuntimeError(
                f"Google Spreadsheet with ID '{self.spreadsheet_id}' was not found.\n"
                f"Please verify the ID and ensure you have shared the sheet with your service account email."
            )
        except Exception as e:
            raise RuntimeError(f"Failed to authenticate with Google Sheets: {e}")

    def _get_or_create_worksheet(self, title: str, rows: int = 100, cols: int = 25):
        import gspread
        try:
            return self.spreadsheet.worksheet(title)
        except gspread.exceptions.WorksheetNotFound:
            ws = self.spreadsheet.add_worksheet(title=title, rows=rows, cols=cols)
            return ws

    def initialize_sheets(self) -> None:
        ws_games = self._get_or_create_worksheet(self.games_log_title, rows=200, cols=25)
        existing_games = ws_games.get_all_values()
        if not existing_games or existing_games[0] != GAMES_LOG_HEADERS:
            ws_games.update(range_name="A1:U1", values=[GAMES_LOG_HEADERS])
            try:
                ws_games.format("A1:U1", {
                    "backgroundColor": {"red": 0.1, "green": 0.2, "blue": 0.4},
                    "textFormat": {"foregroundColor": {"red": 1.0, "green": 1.0, "blue": 1.0}, "bold": True},
                    "horizontalAlignment": "CENTER",
                })
                ws_games.freeze(rows=1)
            except Exception:
                pass

        ws_squares = self._get_or_create_worksheet(self.squares_tracker_title, rows=150, cols=20)
        existing_squares = ws_squares.get_all_values()
        if not existing_squares or len(existing_squares) < 2:
            ws_squares.update(range_name="A1:J1", values=[SQUARES_TRACKER_HEADERS])
            try:
                ws_squares.format("A1:J1", {
                    "backgroundColor": {"red": 0.15, "green": 0.35, "blue": 0.2},
                    "textFormat": {"foregroundColor": {"red": 1.0, "green": 1.0, "blue": 1.0}, "bold": True},
                    "horizontalAlignment": "CENTER",
                })
                ws_squares.freeze(rows=1)
            except Exception:
                pass

    def sync_games_log(self, games: List[GameRecord]) -> int:
        if not games:
            return 0

        ws = self._get_or_create_worksheet(self.games_log_title)
        all_values = ws.get_all_values()

        id_to_row: Dict[str, int] = {}
        if len(all_values) > 1:
            for row_idx, row in enumerate(all_values[1:], start=2):
                if row and row[0]:
                    id_to_row[str(row[0]).strip()] = row_idx

        now_utc = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        updated_count = 0
        new_rows: List[List[Any]] = []
        batch_updates = []

        for game in games:
            row_data = game.to_sheet_row(now_utc)
            gid_str = str(game.game_id)
            if gid_str in id_to_row:
                row_num = id_to_row[gid_str]
                batch_updates.append({
                    "range": f"A{row_num}:U{row_num}",
                    "values": [row_data]
                })
                updated_count += 1
            else:
                new_rows.append(row_data)

        if batch_updates:
            ws.batch_update(batch_updates)
        if new_rows:
            ws.append_rows(new_rows)
            updated_count += len(new_rows)

        return updated_count

    def sync_squares_tracker(self, games: List[GameRecord]) -> int:
        if not games:
            return 0

        ws = self._get_or_create_worksheet(self.squares_tracker_title)
        all_values = ws.get_all_values()

        existing_keys: Dict[str, int] = {}
        if len(all_values) > 1:
            for row_idx, row in enumerate(all_values[1:], start=2):
                if len(row) >= 1 and row[0]:
                    key = str(row[0]).strip()
                    existing_keys[key] = row_idx

        now_utc = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        batch_updates = []
        new_rows = []
        synced_count = 0

        squares_data = build_squares_rows(games, now_utc)
        for sq_row in squares_data:
            key = str(sq_row[0]).strip()
            if key in existing_keys:
                r_num = existing_keys[key]
                batch_updates.append({"range": f"A{r_num}:K{r_num}", "values": [sq_row]})
            else:
                new_rows.append(sq_row)
            synced_count += 1

        if batch_updates:
            ws.batch_update(batch_updates)
        if new_rows:
            ws.append_rows(new_rows)

        return synced_count

    def create_game_board(
        self,
        force: bool = False,
        home_digits: Optional[List[int]] = None,
        away_digits: Optional[List[int]] = None
    ) -> Dict[str, Any]:
        """Creates or initializes the 'game board' tab using Google Cloud service account."""
        import random
        if home_digits is None:
            home_digits = list(range(10))
            random.shuffle(home_digits)
        if away_digits is None:
            away_digits = list(range(10))
            random.shuffle(away_digits)

        title = "game board"
        existing = [ws.title.lower() for ws in self.spreadsheet.worksheets()]
        if "game board" in existing and not force:
            return {"status": "exists", "message": "Tab 'game board' already exists."}

        ws = self._get_or_create_worksheet(title)
        if force:
            ws.clear()

        # Update values: HOME TEAM at C1, AWAY TEAM at A3, Digits at C2:L2 and B3:B12
        cell_updates = [
            {"range": "C1", "values": [["HOME TEAM"]]},
            {"range": "A3", "values": [["AWAY TEAM"]]},
            {"range": "C2:L2", "values": [home_digits]},
            {"range": "B3:B12", "values": [[d] for d in away_digits]},
        ]
        ws.batch_update(cell_updates)
        return {
            "status": "created",
            "message": "Game board created successfully!",
            "homeDigits": home_digits,
            "awayDigits": away_digits,
        }

    def create_payouts_sheet(self, force: bool = False) -> Dict[str, Any]:
        """Creates or initializes the 'Payouts' tab using Google Cloud service account."""
        title = "Payouts"
        existing = [ws.title.lower() for ws in self.spreadsheet.worksheets()]
        if "payouts" in existing and not force:
            return {"status": "exists", "message": "Tab 'Payouts' already exists."}

        ws = self._get_or_create_worksheet(title, rows=110, cols=12)
        if force:
            ws.clear()

        headers = [
            "People playing", "# of squares", "Board Cells",
            "1st Rnd", "2nd Rnd", "Sweet 16", "Elite 8", "Final 4", "FINALS", "Total Won"
        ]
        updates = [
            {"range": "A1:J1", "values": [["Payouts"] * 10]},
            {"range": "A2:J2", "values": [headers]},
            {"range": "A3", "values": [["=IFERROR(SORT(UNIQUE(TOCOL('Game Board'!$C$9:$L$18, 1))), \"\")"]]},
        ]
        b_formulas = [[f'=IF(A{r}="", "", COUNTIF(\'Game Board\'!$C$9:$L$18, A{r}))'] for r in range(3, 103)]
        c_formulas = [[f'=IF(A{r}="", "", TEXTJOIN(", ", TRUE, ARRAYFORMULA(IF(TRIM(\'Game Board\'!$C$9:$L$18)=TRIM(A{r}), ADDRESS(ROW(\'Game Board\'!$C$9:$L$18), COLUMN(\'Game Board\'!$C$9:$L$18), 4), ""))))'] for r in range(3, 103)]
        j_formulas = [[f'=IF(A{r}="", "", IF(SUM(D{r}:I{r})>0, SUM(D{r}:I{r}), ""))'] for r in range(3, 103)]

        ws.batch_update(updates)
        ws.update(range_name="B3:B102", values=b_formulas, value_input_option="USER_ENTERED")
        ws.update(range_name="C3:C102", values=c_formulas, value_input_option="USER_ENTERED")
        ws.update(range_name="J3:J102", values=j_formulas, value_input_option="USER_ENTERED")

        return {
            "status": "created",
            "message": "Payouts sheet created successfully with room for 100 unique players!",
        }


def create_sheets_client(cfg) -> Any:
    """Factory creating either WebhookSheetsClient (Zero GCP) or GoogleSheetsClient (Service Account)."""
    if cfg.use_webhook:
        return WebhookSheetsClient(webhook_url=cfg.google_webhook_url)
    return GoogleSheetsClient(
        service_account_path=cfg.service_account_path,
        spreadsheet_id=cfg.spreadsheet_id,
        games_log_title=cfg.sheet_games_log_name,
        squares_tracker_title=cfg.sheet_squares_tracker_name,
    )
