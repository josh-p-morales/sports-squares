import time
import sys
from typing import Optional, List
from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from config import Config
from .api_client import ApiSportsBasketballClient
from .espn_client import EspnBasketballClient
from .parser import parse_games_list, parse_espn_events_list, GameRecord
from .sheets_client import create_sheets_client
from .mock_data import get_sample_ncaa_games

console = Console()

def display_games_table(games: List[GameRecord]) -> None:
    """Renders a formatted table of games and squares to the terminal."""
    table = Table(title="🏀 College Basketball Games & Squares Summary", show_header=True, header_style="bold magenta")
    table.add_column("ID", style="dim", width=10)
    table.add_column("Status", width=14)
    table.add_column("Round / Region", width=22, style="bold cyan")
    table.add_column("Matchup (Away @ Home)", min_width=30)
    table.add_column("Period Scores (Away / Home)", width=24)
    table.add_column("Total", width=10, justify="center")
    table.add_column("Winning Square (Final)", width=24, style="bold green")
    table.add_column("Winning Cell", width=14, style="bold yellow")

    for g in games:
        # Build score string
        away_scores = []
        home_scores = []
        if g.away_q1 is not None or g.home_q1 is not None:
            lbl1 = "1H" if g.away_q3 is None else "Q1"
            away_scores.append(f"{lbl1}:{g.away_q1 if g.away_q1 is not None else '-'}")
            home_scores.append(f"{lbl1}:{g.home_q1 if g.home_q1 is not None else '-'}")
        if g.away_q2 is not None or g.home_q2 is not None:
            lbl2 = "2H" if g.away_q3 is None else "Q2"
            away_scores.append(f"{lbl2}:{g.away_q2 if g.away_q2 is not None else '-'}")
            home_scores.append(f"{lbl2}:{g.home_q2 if g.home_q2 is not None else '-'}")
        if g.away_q3 is not None or g.home_q3 is not None:
            away_scores.append(f"Q3:{g.away_q3 if g.away_q3 is not None else '-'}")
            home_scores.append(f"Q3:{g.home_q3 if g.home_q3 is not None else '-'}")
        if g.away_q4 is not None or g.home_q4 is not None:
            away_scores.append(f"Q4:{g.away_q4 if g.away_q4 is not None else '-'}")
            home_scores.append(f"Q4:{g.home_q4 if g.home_q4 is not None else '-'}")
        if g.away_ot is not None or g.home_ot is not None:
            away_scores.append(f"OT:{g.away_ot if g.away_ot is not None else '-'}")
            home_scores.append(f"OT:{g.home_ot if g.home_ot is not None else '-'}")

        score_detail = f"{', '.join(away_scores)}\n{', '.join(home_scores)}" if away_scores else "Pending"
        matchup_str = f"{g.away_team}\n@ {g.home_team}"
        total_str = f"{g.away_total if g.away_total is not None else '-'} - {g.home_total if g.home_total is not None else '-'}"

        # Status badge color
        status_style = "yellow"
        if g.is_finished:
            status_style = "green"
        elif g.is_live:
            status_style = "bold red"

        table.add_row(
            str(g.game_id),
            f"[{status_style}]{g.status_long}[/{status_style}]",
            g.tournament_round or "-",
            matchup_str,
            score_detail,
            total_str,
            g.final_square or "-",
            g.winning_cell or "-",
        )

    console.print(table)


def execute_sync(
    config: Config,
    date_str: Optional[str] = None,
    year: Optional[int] = None,
    tournament_only: bool = False,
    round_filter: Optional[str] = None,
    league_id: Optional[int] = None,
    season: Optional[str] = None,
    gender: Optional[str] = None,
    source: Optional[str] = None,
    live_only: bool = False,
    mock_mode: bool = False,
    skip_sheets: bool = False,
) -> List[GameRecord]:
    """Fetches games from ESPN (or API-Sports/mock), parses them, and pushes to Google Sheets."""
    active_source = (source or config.data_source).lower()
    target_gender = (gender or config.espn_league).lower()

    if year:
        console.print(
            f"[bold blue]ℹ Fetching March Madness Tournament:[/bold blue] Year=[bold yellow]{year}[/bold yellow], "
            f"League/Gender={target_gender}, RoundFilter={round_filter or 'All'}"
        )
    else:
        target_date = date_str or datetime.utcnow().strftime("%Y-%m-%d")
        console.print(
            f"[bold blue]ℹ Fetching games:[/bold blue] Source=[bold cyan]{active_source.upper()}[/bold cyan], "
            f"League/Gender={target_gender}, Date={target_date}, TournamentOnly={tournament_only}, LiveOnly={live_only}, Mock={mock_mode}"
        )

    if mock_mode:
        raw_games = get_sample_ncaa_games()
        games = parse_games_list(raw_games)
    elif active_source == "espn":
        is_womens = "women" in target_gender
        client = EspnBasketballClient(league_type=target_gender)

        if year:
            with console.status(f"[bold cyan]Harvesting {target_gender.capitalize()} March Madness games for {year}...[/bold cyan]") as status:
                def on_progress(d, current, total):
                    status.update(f"[bold cyan]Querying tournament date {d} ({current}/{total})...[/bold cyan]")
                events = client.get_tournament_games(year=year, on_progress=on_progress)
        else:
            events = client.get_scoreboard(date_str=target_date, tournament_only=tournament_only)

        games = parse_espn_events_list(events, is_womens=is_womens)
        if live_only:
            games = [g for g in games if g.is_live]
    else:
        # API-Sports fallback
        target_league = league_id or config.default_league_id
        target_season = season or config.default_season
        config.validate_api_key()
        client = ApiSportsBasketballClient(api_key=config.api_sports_key, base_url=config.api_base_url)
        raw_games = client.get_games(
            date_str=None if live_only else (date_str or datetime.utcnow().strftime("%Y-%m-%d")),
            league_id=target_league,
            season=target_season,
            live="all" if live_only else None,
        )
        games = parse_games_list(raw_games)

    # Apply round filter if specified
    if round_filter:
        rf_lower = round_filter.strip().lower()
        games = [g for g in games if rf_lower in (g.tournament_round or "").lower()]

    console.print(f"[green]✓ Found {len(games)} game(s)[/green]")

    if not games:
        console.print("[yellow]No games matched your criteria.[/yellow]")
        return []

    display_games_table(games)

    if not skip_sheets and games:
        final_games = [g for g in games if g.is_finished]
        if not final_games:
            console.print("[yellow]ℹ No completed games found. Only final scores are synced to Google Sheets.[/yellow]")
            return games

        config.validate_sheets_config()
        mode_label = "Google Apps Script Webhook (Zero GCP)" if config.use_webhook else "Service Account"
        console.print(f"[bold yellow]Connecting to Google Sheets via {mode_label} (Syncing {len(final_games)} Final Game(s))...[/bold yellow]")
        
        sheets_client = create_sheets_client(config)
        sheets_client.initialize_sheets()

        if hasattr(sheets_client, "sync_all"):
            res = sheets_client.sync_all(final_games)
            log_count = res.get("games", 0)
            squares_count = res.get("squares", 0)
        else:
            log_count = sheets_client.sync_games_log(final_games)
            squares_count = sheets_client.sync_squares_tracker(final_games)

        console.print(f"[bold green]✓ Google Sheets updated:[/bold green] {log_count} final game(s) logged, {squares_count} final square(s) updated.")

    return games


def execute_polling(
    config: Config,
    poll_interval: Optional[int] = None,
    league_id: Optional[int] = None,
    season: Optional[str] = None,
    gender: Optional[str] = None,
    source: Optional[str] = None,
    tournament_only: bool = False,
    round_filter: Optional[str] = None,
    mock_mode: bool = False,
    skip_sheets: bool = False,
) -> None:
    """Continuously polls for game updates and refreshes Google Sheets."""
    interval = poll_interval or config.poll_interval_seconds
    active_source = (source or config.data_source).upper()
    sub_title = "March Madness Tournament" if tournament_only else "College Basketball"
    console.print(
        Panel.fit(
            f"[bold green]Starting Live Polling Service ({sub_title})[/bold green]\n"
            f"Source: [bold cyan]{active_source}[/bold cyan] | Gender: [cyan]{gender or config.espn_league}[/cyan] | Interval: [cyan]{interval}s[/cyan]\n"
            f"Press [bold red]Ctrl+C[/bold red] to stop.",
            title="🏀 Sports Squares Runner"
        )
    )

    iteration = 1
    try:
        while True:
            console.rule(f"[bold yellow]Poll #{iteration} - {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}[/bold yellow]")
            try:
                execute_sync(
                    config=config,
                    tournament_only=tournament_only,
                    round_filter=round_filter,
                    league_id=league_id,
                    season=season,
                    gender=gender,
                    source=source,
                    live_only=False,
                    mock_mode=mock_mode,
                    skip_sheets=skip_sheets,
                )
            except Exception as e:
                console.print(f"[bold red]Sync error on iteration #{iteration}:[/bold red] {e}")

            iteration += 1
            console.print(f"[dim]Waiting {interval} seconds until next check...[/dim]")
            time.sleep(interval)
    except KeyboardInterrupt:
        console.print("\n[bold yellow]Polling stopped by user. Exiting gracefully.[/bold yellow]")
