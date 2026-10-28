import requests
from typing import Dict, Any, List, Optional
from rich.console import Console

console = Console()

class ApiSportsBasketballClient:
    """Client for API-Sports Basketball (v1.basketball.api-sports.io)."""

    def __init__(self, api_key: str, base_url: str = "https://v1.basketball.api-sports.io"):
        self.api_key = api_key.strip()
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({
            "x-apisports-key": self.api_key,
            "User-Agent": "SportsSquares/1.0"
        })

    def _request(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Performs a GET request to api-sports.io and validates the response."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        try:
            response = self.session.get(url, params=params, timeout=20)
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"HTTP request to API-Sports failed: {e}")

        # Check for API-level errors
        errors = data.get("errors", {})
        if errors:
            if isinstance(errors, dict) and len(errors) > 0:
                err_msgs = [f"{k}: {v}" for k, v in errors.items()]
                raise RuntimeError(f"API-Sports Error: {', '.join(err_msgs)}")
            elif isinstance(errors, list) and len(errors) > 0:
                raise RuntimeError(f"API-Sports Error: {', '.join(map(str, errors))}")

        return data

    def get_status(self) -> Dict[str, Any]:
        """Fetches account/API status, active plan, and daily request quota."""
        data = self._request("status")
        return data.get("response", {})

    def get_leagues(self, search: Optional[str] = None, country: Optional[str] = None) -> List[Dict[str, Any]]:
        """Fetches basketball leagues with optional name search or country filter."""
        params: Dict[str, Any] = {}
        if search:
            params["search"] = search
        if country:
            params["country"] = country
        data = self._request("leagues", params=params)
        return data.get("response", [])

    def get_games(
        self,
        date_str: Optional[str] = None,
        league_id: Optional[int] = None,
        season: Optional[str] = None,
        game_id: Optional[int] = None,
        live: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Fetches basketball games matching the criteria.
        
        Args:
            date_str: Date in 'YYYY-MM-DD' format
            league_id: League identifier (e.g., 116 for NCAA)
            season: Season string (e.g., '2025-2026')
            game_id: Specific game ID
            live: 'all' to get live games
        """
        params: Dict[str, Any] = {}
        if date_str:
            params["date"] = date_str
        if league_id is not None:
            params["league"] = str(league_id)
        if season:
            params["season"] = str(season)
        if game_id is not None:
            params["id"] = str(game_id)
        if live:
            params["live"] = live

        data = self._request("games", params=params)
        return data.get("response", [])
