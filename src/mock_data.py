from typing import List, Dict, Any

def get_sample_ncaa_games() -> List[Dict[str, Any]]:
    """Returns sample NCAA College Basketball games with realistic period scores for testing."""
    return [
        {
            "id": 481001,
            "date": "2026-03-22T18:15:00+00:00",
            "time": "18:15",
            "timestamp": 1774203300,
            "timezone": "UTC",
            "status": {"short": "FT", "long": "Finished", "timer": None},
            "league": {"id": 116, "name": "NCAA", "type": "League", "season": "2025-2026"},
            "teams": {
                "away": {"id": 101, "name": "North Carolina Tar Heels"},
                "home": {"id": 102, "name": "Duke Blue Devils"}
            },
            "scores": {
                "away": {"quarter_1": 39, "quarter_2": 44, "quarter_3": None, "quarter_4": None, "over_time": None, "total": 83},
                "home": {"quarter_1": 41, "quarter_2": 40, "quarter_3": None, "quarter_4": None, "over_time": None, "total": 81}
            }
        },
        {
            "id": 481002,
            "date": "2026-03-22T20:45:00+00:00",
            "time": "20:45",
            "timestamp": 1774212300,
            "timezone": "UTC",
            "status": {"short": "HT", "long": "Half Time", "timer": None},
            "league": {"id": 116, "name": "NCAA", "type": "League", "season": "2025-2026"},
            "teams": {
                "away": {"id": 103, "name": "Kansas Jayhawks"},
                "home": {"id": 104, "name": "Kentucky Wildcats"}
            },
            "scores": {
                "away": {"quarter_1": 36, "quarter_2": None, "quarter_3": None, "quarter_4": None, "over_time": None, "total": 36},
                "home": {"quarter_1": 38, "quarter_2": None, "quarter_3": None, "quarter_4": None, "over_time": None, "total": 38}
            }
        },
        {
            "id": 481003,
            "date": "2026-03-22T21:00:00+00:00",
            "time": "21:00",
            "timestamp": 1774213200,
            "timezone": "UTC",
            "status": {"short": "AOT", "long": "After Over Time", "timer": None},
            "league": {"id": 116, "name": "NCAA", "type": "League", "season": "2025-2026"},
            "teams": {
                "away": {"id": 105, "name": "UConn Huskies"},
                "home": {"id": 106, "name": "Gonzaga Bulldogs"}
            },
            "scores": {
                "away": {"quarter_1": 35, "quarter_2": 37, "quarter_3": None, "quarter_4": None, "over_time": 12, "total": 84},
                "home": {"quarter_1": 32, "quarter_2": 40, "quarter_3": None, "quarter_4": None, "over_time": 10, "total": 82}
            }
        },
        {
            "id": 481004,
            "date": "2026-03-22T22:30:00+00:00",
            "time": "22:30",
            "timestamp": 1774218600,
            "timezone": "UTC",
            "status": {"short": "NS", "long": "Not Started", "timer": None},
            "league": {"id": 116, "name": "NCAA", "type": "League", "season": "2025-2026"},
            "teams": {
                "away": {"id": 107, "name": "Houston Cougars"},
                "home": {"id": 108, "name": "Arizona Wildcats"}
            },
            "scores": {
                "away": {"quarter_1": None, "quarter_2": None, "quarter_3": None, "quarter_4": None, "over_time": None, "total": None},
                "home": {"quarter_1": None, "quarter_2": None, "quarter_3": None, "quarter_4": None, "over_time": None, "total": None}
            }
        }
    ]
