import requests
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, date, timedelta

class EspnBasketballClient:
    """
    Client for ESPN's public College Basketball API.
    Does not require any API key or account registration.
    """

    MENS_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/scoreboard"
    WOMENS_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/womens-college-basketball/scoreboard"

    def __init__(self, league_type: str = "mens"):
        self.league_type = league_type.lower()
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) SportsSquares/2.0"
        })

    @property
    def endpoint_url(self) -> str:
        if "women" in self.league_type:
            return self.WOMENS_URL
        return self.MENS_URL

    def get_scoreboard(
        self,
        date_str: Optional[str] = None,
        groups: Optional[int] = 50,  # 50 = NCAA Division I, 100 = NCAA Tournament (March Madness)
        tournament_only: bool = False,
        limit: int = 300,
    ) -> List[Dict[str, Any]]:
        """
        Fetches college basketball scoreboard for a specific date (or today).

        Args:
            date_str: Date formatted as 'YYYY-MM-DD' or 'YYYYMMDD'. If None, fetches current live/today.
            groups: Division group (50 is NCAA Div I, 100 is NCAA Tournament).
            tournament_only: If True, overrides groups to 100 (March Madness only).
            limit: Maximum games to return (default 300 to ensure all games in a day are included).
        """
        params: Dict[str, Any] = {"limit": limit}

        if date_str:
            cleaned_date = date_str.replace("-", "").strip()
            params["dates"] = cleaned_date

        if tournament_only:
            params["groups"] = 100
        elif groups is not None:
            params["groups"] = groups

        try:
            response = self.session.get(self.endpoint_url, params=params, timeout=20)
            response.raise_for_status()
            data = response.json()
            return data.get("events", [])
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Failed to fetch scoreboard from ESPN: {e}")

    def get_tournament_dates(self, year: int) -> List[str]:
        """
        Retrieves all active tournament game dates from ESPN's league calendar for a given year.
        March Madness spans between mid-March (Selection Sunday/First Four) and early April (National Championship).
        """
        try:
            # Query a sample mid-tournament date to retrieve that year's season calendar
            res = self.session.get(self.endpoint_url, params={"dates": f"{year}0322", "limit": 1}, timeout=15)
            res.raise_for_status()
            data = res.json()
            leagues = data.get("leagues", [])
            calendar = leagues[0].get("calendar", []) if leagues else []
        except Exception:
            calendar = []

        start_prefix = f"{year}-03-12"
        end_prefix = f"{year}-04-15"
        tournament_dates = []

        for d in calendar:
            if isinstance(d, str):
                date_str = d.split("T")[0]
                if start_prefix <= date_str <= end_prefix:
                    tournament_dates.append(date_str.replace("-", ""))

        # Fallback to date range scan if calendar is empty
        if not tournament_dates:
            cur = date(year, 3, 14)
            end = date(year, 4, 10)
            while cur <= end:
                tournament_dates.append(cur.strftime("%Y%m%d"))
                cur += timedelta(days=1)

        return sorted(list(set(tournament_dates)))

    def get_tournament_games(
        self,
        year: int,
        on_progress: Optional[Callable[[str, int, int], None]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Fetches all March Madness tournament games for a given year.
        Iterates over the tournament calendar dates using groups=100.
        """
        dates = self.get_tournament_dates(year)
        seen_ids = set()
        all_events = []

        for idx, d in enumerate(dates, start=1):
            if on_progress:
                on_progress(d, idx, len(dates))
            events = self.get_scoreboard(date_str=d, groups=100, limit=100)
            for ev in events:
                eid = ev.get("id")
                if eid and eid not in seen_ids:
                    seen_ids.add(eid)
                    all_events.append(ev)

        return all_events

    def test_connection(self) -> Dict[str, Any]:
        """Pings ESPN endpoint to verify connectivity."""
        try:
            response = self.session.get(self.endpoint_url, params={"limit": 1}, timeout=10)
            response.raise_for_status()
            data = response.json()
            league_info = data.get("leagues", [{}])[0]
            return {
                "status": "ok",
                "league": league_info.get("name", "NCAA Men's Basketball"),
                "season": league_info.get("season", {}).get("year", "Current"),
            }
        except Exception as e:
            raise RuntimeError(f"ESPN API connection check failed: {e}")
