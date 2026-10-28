from dataclasses import dataclass
from typing import Dict, Any, Optional, List
from datetime import datetime

@dataclass
class GameRecord:
    game_id: int
    date: str
    time: str
    status_short: str
    status_long: str
    league_name: str
    season: str
    away_team: str
    home_team: str

    # Period scores
    away_q1: Optional[int]
    away_q2: Optional[int]
    away_q3: Optional[int]
    away_q4: Optional[int]
    away_ot: Optional[int]
    away_total: Optional[int]

    home_q1: Optional[int]
    home_q2: Optional[int]
    home_q3: Optional[int]
    home_q4: Optional[int]
    home_ot: Optional[int]
    home_total: Optional[int]

    # Tournament info
    tournament_round: Optional[str] = None  # e.g., "Midwest Region - 1st Round", "Final Four"

    # Derived Halftime and Final totals
    away_ht: Optional[int] = None
    home_ht: Optional[int] = None

    # Squares winning digits (last digit of score: 0-9)
    ht_square: Optional[str] = None      # e.g., "A3-H7"
    final_square: Optional[str] = None   # e.g., "A5-H1"

    @property
    def is_finished(self) -> bool:
        return self.status_short in {"FT", "AOT", "POST", "CANC", "AET"}

    @property
    def is_live(self) -> bool:
        return self.status_short in {"Q1", "Q2", "Q3", "Q4", "OT", "BT", "HT", "LIVE", "1H", "2H"}

    @property
    def winning_cell(self) -> Optional[str]:
        """Calculates winning cell coordinate on the Game Board (e.g. A0-H0 -> C9, A0-H9 -> L9, A9-H0 -> C18)."""
        if self.away_total is not None and self.home_total is not None and self.is_finished:
            col_letters = ["C", "D", "E", "F", "G", "H", "I", "J", "K", "L"]
            col = col_letters[self.home_total % 10]
            row = 9 + (self.away_total % 10)
            return f"{col}{row}"
        return None

    def to_sheet_row(self, last_updated: str) -> List[Any]:
        """Formats the game into a row for the 'Games Log' tab."""
        return [
            self.game_id,
            self.date,
            self.time,
            self.status_long or self.status_short,
            self.tournament_round or "",
            self.away_team,
            "" if self.away_q1 is None else self.away_q1,
            "" if self.away_q2 is None else self.away_q2,
            "" if self.away_q3 is None else self.away_q3,
            "" if self.away_q4 is None else self.away_q4,
            "" if self.away_ot is None else self.away_ot,
            "" if self.away_total is None else self.away_total,
            self.home_team,
            "" if self.home_q1 is None else self.home_q1,
            "" if self.home_q2 is None else self.home_q2,
            "" if self.home_q3 is None else self.home_q3,
            "" if self.home_q4 is None else self.home_q4,
            "" if self.home_ot is None else self.home_ot,
            "" if self.home_total is None else self.home_total,
            "" if not self.final_square else self.final_square,
            "" if not self.winning_cell else self.winning_cell,
            last_updated,
        ]


def parse_game(raw: Dict[str, Any]) -> GameRecord:
    """Parses a single raw game JSON object from API-Sports Basketball."""
    game_id = raw.get("id", 0)
    raw_date = raw.get("date", "")
    time_str = raw.get("time", "")

    # Format human-readable date if possible
    formatted_date = raw_date
    if "T" in raw_date:
        try:
            dt = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
            formatted_date = dt.strftime("%Y-%m-%d")
            if not time_str:
                time_str = dt.strftime("%H:%M UTC")
        except Exception:
            formatted_date = raw_date.split("T")[0]

    status_data = raw.get("status", {})
    status_short = status_data.get("short", "NS")
    status_long = status_data.get("long", "Not Started")

    league_data = raw.get("league", {})
    league_name = league_data.get("name", "NCAA")
    season = str(league_data.get("season", ""))

    teams = raw.get("teams", {})
    away_team = teams.get("away", {}).get("name", "Away")
    home_team = teams.get("home", {}).get("name", "Home")

    scores = raw.get("scores", {})
    away_scores = scores.get("away", {})
    home_scores = scores.get("home", {})

    away_q1 = away_scores.get("quarter_1")
    away_q2 = away_scores.get("quarter_2")
    away_q3 = away_scores.get("quarter_3")
    away_q4 = away_scores.get("quarter_4")
    away_ot = away_scores.get("over_time")
    away_total = away_scores.get("total")

    home_q1 = home_scores.get("quarter_1")
    home_q2 = home_scores.get("quarter_2")
    home_q3 = home_scores.get("quarter_3")
    home_q4 = home_scores.get("quarter_4")
    home_ot = home_scores.get("over_time")
    home_total = home_scores.get("total")

    # Compute Halftime Score
    # For Men's NCAA (2 halves): Q1 is 1H
    # For Women's NCAA (4 quarters): Q1 + Q2 is Halftime
    away_ht = None
    home_ht = None

    if away_q3 is not None or home_q3 is not None or away_q4 is not None or home_q4 is not None:
        # 4-quarter style game (e.g. Women's NCAA)
        if away_q1 is not None and away_q2 is not None:
            away_ht = away_q1 + away_q2
        if home_q1 is not None and home_q2 is not None:
            home_ht = home_q1 + home_q2
    else:
        # 2-half style game (e.g. Men's NCAA)
        if away_q1 is not None:
            away_ht = away_q1
        if home_q1 is not None:
            home_ht = home_q1

    # Calculate Winning Squares (last digit: % 10)
    ht_square = None
    if away_ht is not None and home_ht is not None:
        away_digit = away_ht % 10
        home_digit = home_ht % 10
        ht_square = f"Away {away_digit} - Home {home_digit} (A{away_digit}-H{home_digit})"

    final_square = None
    if away_total is not None and home_total is not None and (status_short in {"FT", "AOT"} or raw.get("status", {}).get("long") == "Finished"):
        away_digit = away_total % 10
        home_digit = home_total % 10
        final_square = f"Away {away_digit} - Home {home_digit} (A{away_digit}-H{home_digit})"

    return GameRecord(
        game_id=game_id,
        date=formatted_date,
        time=time_str,
        status_short=status_short,
        status_long=status_long,
        league_name=league_name,
        season=season,
        away_team=away_team,
        home_team=home_team,
        away_q1=away_q1,
        away_q2=away_q2,
        away_q3=away_q3,
        away_q4=away_q4,
        away_ot=away_ot,
        away_total=away_total,
        home_q1=home_q1,
        home_q2=home_q2,
        home_q3=home_q3,
        home_q4=home_q4,
        home_ot=home_ot,
        home_total=home_total,
        away_ht=away_ht,
        home_ht=home_ht,
        ht_square=ht_square,
        final_square=final_square,
    )


def parse_games_list(games_raw: List[Dict[str, Any]]) -> List[GameRecord]:
    """Parses a list of game responses from API-Sports."""
    return [parse_game(g) for g in games_raw]


def parse_espn_event(event: Dict[str, Any], is_womens: bool = False) -> GameRecord:
    """Parses a single ESPN college basketball event into a GameRecord."""
    game_id_str = event.get("id", "0")
    try:
        game_id = int(game_id_str)
    except ValueError:
        game_id = hash(game_id_str) % (10 ** 8)

    raw_date = event.get("date", "")
    formatted_date = raw_date
    time_str = ""
    if "T" in raw_date:
        try:
            dt = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
            formatted_date = dt.strftime("%Y-%m-%d")
            time_str = dt.strftime("%H:%M UTC")
        except Exception:
            formatted_date = raw_date.split("T")[0]

    competition = event.get("competitions", [{}])[0]
    status_data = competition.get("status", {})
    status_type = status_data.get("type", {})
    state = status_type.get("state", "pre")  # 'pre', 'in', 'post'
    completed = status_type.get("completed", False)
    short_detail = status_type.get("shortDetail", "")
    long_detail = status_type.get("detail", "")
    period = status_data.get("period", 0)

    # Determine status_short
    if completed or state == "post":
        status_short = "FT"
    elif "half" in short_detail.lower() and period == 1 and status_data.get("displayClock") == "0:00":
        status_short = "HT"
    elif state == "in":
        status_short = f"P{period}" if period else "LIVE"
    else:
        status_short = "NS"

    status_long = long_detail or short_detail or ("Finished" if completed else "Scheduled")

    competitors = competition.get("competitors", [])
    home_comp = {}
    away_comp = {}
    for c in competitors:
        if c.get("homeAway") == "home":
            home_comp = c
        else:
            away_comp = c

    home_team = home_comp.get("team", {}).get("displayName", "Home")
    away_team = away_comp.get("team", {}).get("displayName", "Away")

    # Parse Total Scores
    def parse_int_score(val) -> Optional[int]:
        if val is None or val == "":
            return None
        try:
            return int(float(val))
        except (ValueError, TypeError):
            return None

    home_total = parse_int_score(home_comp.get("score"))
    away_total = parse_int_score(away_comp.get("score"))

    # Parse Linescores (period scores)
    def extract_lines(comp) -> List[int]:
        res = []
        for ls in comp.get("linescores", []):
            v = parse_int_score(ls.get("value"))
            if v is not None:
                res.append(v)
        return res

    home_lines = extract_lines(home_comp)
    away_lines = extract_lines(away_comp)

    # Determine Men's vs Women's structure
    # Women's has 4 quarters; Men's has 2 halves
    if is_womens:
        away_q1 = away_lines[0] if len(away_lines) > 0 else None
        away_q2 = away_lines[1] if len(away_lines) > 1 else None
        away_q3 = away_lines[2] if len(away_lines) > 2 else None
        away_q4 = away_lines[3] if len(away_lines) > 3 else None
        away_ot = sum(away_lines[4:]) if len(away_lines) > 4 else None

        home_q1 = home_lines[0] if len(home_lines) > 0 else None
        home_q2 = home_lines[1] if len(home_lines) > 1 else None
        home_q3 = home_lines[2] if len(home_lines) > 2 else None
        home_q4 = home_lines[3] if len(home_lines) > 3 else None
        home_ot = sum(home_lines[4:]) if len(home_lines) > 4 else None

        away_ht = (away_q1 + away_q2) if (away_q1 is not None and away_q2 is not None) else None
        home_ht = (home_q1 + home_q2) if (home_q1 is not None and home_q2 is not None) else None
    else:
        # Men's College Basketball (2 Halves)
        away_q1 = away_lines[0] if len(away_lines) > 0 else None
        away_q2 = away_lines[1] if len(away_lines) > 1 else None
        away_q3 = None
        away_q4 = None
        away_ot = sum(away_lines[2:]) if len(away_lines) > 2 else None

        home_q1 = home_lines[0] if len(home_lines) > 0 else None
        home_q2 = home_lines[1] if len(home_lines) > 1 else None
        home_q3 = None
        home_q4 = None
        home_ot = sum(home_lines[2:]) if len(home_lines) > 2 else None

        away_ht = away_q1
        home_ht = home_q1

    # Squares calculation (last digit: % 10)
    ht_square = None
    if away_ht is not None and home_ht is not None:
        a_dig = away_ht % 10
        h_dig = home_ht % 10
        ht_square = f"Away {a_dig} - Home {h_dig} (A{a_dig}-H{h_dig})"

    final_square = None
    if away_total is not None and home_total is not None and (completed or state == "post"):
        a_dig = away_total % 10
        h_dig = home_total % 10
        final_square = f"Away {a_dig} - Home {h_dig} (A{a_dig}-H{h_dig})"

    # Tournament Round Extraction from competition notes
    notes = competition.get("notes", [])
    tournament_round = None
    if notes and isinstance(notes, list):
        for n in notes:
            headline = n.get("headline", "")
            if headline:
                cleaned = headline
                for prefix in [
                    "Men's Basketball Championship - ",
                    "Women's Basketball Championship - ",
                    "NCAA Men's Basketball Championship - ",
                    "NCAA Women's Basketball Championship - ",
                ]:
                    if cleaned.startswith(prefix):
                        cleaned = cleaned[len(prefix):]
                tournament_round = cleaned.strip()
                break

    league_name = "NCAA Women" if is_womens else "NCAA Men"

    return GameRecord(
        game_id=game_id,
        date=formatted_date,
        time=time_str,
        status_short=status_short,
        status_long=status_long,
        tournament_round=tournament_round,
        league_name=league_name,
        season=str(event.get("season", {}).get("year", "")),
        away_team=away_team,
        home_team=home_team,
        away_q1=away_q1,
        away_q2=away_q2,
        away_q3=away_q3,
        away_q4=away_q4,
        away_ot=away_ot,
        away_total=away_total,
        home_q1=home_q1,
        home_q2=home_q2,
        home_q3=home_q3,
        home_q4=home_q4,
        home_ot=home_ot,
        home_total=home_total,
        away_ht=away_ht,
        home_ht=home_ht,
        ht_square=ht_square,
        final_square=final_square,
    )


def parse_espn_events_list(events_raw: List[Dict[str, Any]], is_womens: bool = False) -> List[GameRecord]:
    """Parses a list of ESPN events."""
    return [parse_espn_event(e, is_womens=is_womens) for e in events_raw]

