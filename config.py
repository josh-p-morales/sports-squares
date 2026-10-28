import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from project root
load_dotenv()

@dataclass
class Config:
    # Data Source: "espn" (default, free, no API key needed) or "api-sports"
    data_source: str = os.getenv("DATA_SOURCE", "espn").lower()
    espn_league: str = os.getenv("ESPN_LEAGUE", "mens").lower()  # "mens" or "womens"

    # API-Sports (Only needed if DATA_SOURCE=api-sports)
    api_sports_key: str = os.getenv("API_SPORTS_KEY", "")
    api_base_url: str = os.getenv("API_BASE_URL", "https://v1.basketball.api-sports.io")

    # Google Sheets Connection Options:
    # Option A (Recommended): Google Apps Script Web App URL (Zero Google Cloud required)
    google_webhook_url: str = os.getenv("GOOGLE_WEBHOOK_URL", "")

    # Option B: Google Cloud Service Account
    service_account_path: str = os.getenv("GOOGLE_SERVICE_ACCOUNT_PATH", "service_account.json")
    spreadsheet_id: str = os.getenv("GOOGLE_SPREADSHEET_ID", "")

    # Sheet tabs
    sheet_games_log_name: str = os.getenv("SHEET_GAMES_LOG_NAME", "Games Log")
    sheet_squares_tracker_name: str = os.getenv("SHEET_SQUARES_TRACKER_NAME", "Squares Tracker")

    # League & Game settings
    default_league_id: int = int(os.getenv("DEFAULT_LEAGUE_ID", "116"))
    default_season: str = os.getenv("DEFAULT_SEASON", "2025-2026")
    poll_interval_seconds: int = int(os.getenv("POLL_INTERVAL_SECONDS", "60"))

    @property
    def use_webhook(self) -> bool:
        return bool(self.google_webhook_url and self.google_webhook_url.strip() and "script.google.com" in self.google_webhook_url)

    def validate_api_key(self) -> None:
        if self.data_source == "api-sports":
            if not self.api_sports_key or self.api_sports_key == "your_apisports_api_key_here":
                raise ValueError(
                    "Missing API_SPORTS_KEY in environment or .env file.\n"
                    "Please get an API key at https://dashboard.api-sports.io/ and add it to your .env file,\n"
                    "or set DATA_SOURCE=espn to use free ESPN data without an API key!"
                )

    def validate_sheets_config(self) -> None:
        if self.use_webhook:
            return  # Webhook URL is present and valid!

        # Fallback to Service Account verification
        sa_path = Path(self.service_account_path)
        has_sa = sa_path.exists()
        has_sheet_id = bool(self.spreadsheet_id and self.spreadsheet_id != "your_google_spreadsheet_id_here")

        if not has_sa and not has_sheet_id:
            raise ValueError(
                "No Google Sheets connection method configured in your .env file.\n"
                "Recommended (Zero Google Cloud setup):\n"
                "  1. Paste google_apps_script.js into your Google Sheet (Extensions > Apps Script)\n"
                "  2. Deploy as Web App and set GOOGLE_WEBHOOK_URL in .env\n\n"
                "Alternative (Google Cloud Service Account):\n"
                "  Set GOOGLE_SERVICE_ACCOUNT_PATH and GOOGLE_SPREADSHEET_ID in .env"
            )
        elif not has_sheet_id:
            raise ValueError("Missing GOOGLE_SPREADSHEET_ID in .env file.")
        elif not has_sa:
            raise FileNotFoundError(
                f"Google Service Account key file not found at: '{self.service_account_path}'.\n"
                f"Tip: If you don't want to use Google Cloud, use GOOGLE_WEBHOOK_URL instead!"
            )

config = Config()
