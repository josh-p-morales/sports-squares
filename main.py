import sys
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import argparse
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from config import config
from src.runner import execute_sync, execute_polling
from src.api_client import ApiSportsBasketballClient
from src.espn_client import EspnBasketballClient
from src.sheets_client import GoogleSheetsClient

console = Console()

def cmd_fetch(args: argparse.Namespace) -> None:
    """Handles the 'fetch' command."""
    execute_sync(
        config=config,
        date_str=args.date,
        year=args.year,
        tournament_only=args.tournament or bool(args.year),
        round_filter=args.round,
        league_id=args.league,
        season=args.season,
        gender=args.gender,
        source=args.source,
        live_only=args.live,
        mock_mode=args.mock,
        skip_sheets=args.dry_run,
    )

def cmd_poll(args: argparse.Namespace) -> None:
    """Handles the 'poll' command."""
    execute_polling(
        config=config,
        poll_interval=args.interval,
        tournament_only=args.tournament,
        round_filter=args.round,
        league_id=args.league,
        season=args.season,
        gender=args.gender,
        source=args.source,
        mock_mode=args.mock,
        skip_sheets=args.dry_run,
    )

def cmd_list_leagues(args: argparse.Namespace) -> None:
    """Displays supported leagues / divisions."""
    if config.data_source == "espn":
        table = Table(title="🏀 ESPN College Basketball Leagues Supported", show_header=True, header_style="bold cyan")
        table.add_column("Gender / Flag", style="bold green", width=20)
        table.add_column("Competition", width=35)
        table.add_column("Period Format", width=25)
        table.add_column("CLI Usage", width=30)

        table.add_row("mens (default)", "NCAA Men's College Basketball", "Two 20-min halves + OT", "--gender mens")
        table.add_row("womens", "NCAA Women's College Basketball", "Four 10-min quarters + OT", "--gender womens")
        console.print(table)
        console.print("\n[dim]Tip: ESPN does not require numeric league IDs or API keys. Simply specify --gender mens or --gender womens.[/dim]")
        return

    config.validate_api_key()
    client = ApiSportsBasketballClient(api_key=config.api_sports_key, base_url=config.api_base_url)
    
    search_term = args.search or "NCAA"
    console.print(f"[bold blue]Searching API-Sports leagues with keyword:[/bold blue] '{search_term}'...")
    leagues = client.get_leagues(search=search_term)

    if not leagues:
        console.print("[yellow]No leagues found matching your search.[/yellow]")
        return

    table = Table(title=f"Basketball Leagues matching '{search_term}'", show_header=True, header_style="bold cyan")
    table.add_column("League ID", style="bold green", width=12)
    table.add_column("League Name", width=30)
    table.add_column("Type", width=12)
    table.add_column("Country", width=15)
    table.add_column("Seasons Available", width=30)

    for item in leagues:
        lid = str(item.get("id", ""))
        name = item.get("name", "")
        ltype = item.get("type", "")
        country = item.get("country", {}).get("name", "")
        seasons = item.get("seasons", [])
        season_strs = [s.get("season", "") for s in seasons if isinstance(s, dict)]
        recent_seasons = ", ".join(season_strs[-3:]) if season_strs else "None"

        table.add_row(lid, name, ltype, country, recent_seasons)

    console.print(table)

def cmd_test(args: argparse.Namespace) -> None:
    """Tests credentials and connectivity to ESPN, API-Sports, and Google Sheets."""
    console.print(Panel.fit("[bold cyan]Running Diagnostic Checks[/bold cyan]", title="Sports Squares"))
    
    # 1. ESPN test (Default free data source)
    console.print("\n[bold]1. Checking ESPN College Basketball API (Free, No Key Required)...[/bold]")
    try:
        espn = EspnBasketballClient()
        espn_info = espn.test_connection()
        console.print(f"  [green]✓ Connected successfully to ESPN API[/green]")
        console.print(f"    League: {espn_info.get('league')} (Season {espn_info.get('season')})")
    except Exception as e:
        console.print(f"  [red]✗ ESPN check failed:[/red] {e}")

    # 2. API-Sports test (Optional fallback)
    if config.api_sports_key and config.api_sports_key != "your_apisports_api_key_here":
        console.print("\n[bold]2. Checking API-Sports.io connection (Optional Fallback)...[/bold]")
        try:
            client = ApiSportsBasketballClient(api_key=config.api_sports_key, base_url=config.api_base_url)
            status_info = client.get_status()
            account = status_info.get("account", {})
            sub = status_info.get("subscription", {})
            requests_info = status_info.get("requests", {})

            console.print(f"  [green]✓ Connected successfully to API-Sports[/green]")
            console.print(f"    Account Email: {account.get('email', 'N/A')}")
            console.print(f"    Plan: {sub.get('plan', 'Free')} (Active: {sub.get('active', True)})")
            console.print(f"    Daily Requests Used: {requests_info.get('current', 0)} / {requests_info.get('limit_day', 100)}")
        except Exception as e:
            console.print(f"  [yellow]⚠ API-Sports check failed:[/yellow] {e}")

    # 3. Google Sheets test
    console.print("\n[bold]3. Checking Google Sheets connection...[/bold]")
    try:
        config.validate_sheets_config()
        if config.use_webhook:
            console.print("  [cyan]Testing Google Apps Script Webhook (Zero GCP mode)...[/cyan]")
            from src.sheets_client import WebhookSheetsClient
            client = WebhookSheetsClient(config.google_webhook_url)
            info = client.test_connection()
            console.print(f"  [green]✓ Connected successfully to Google Spreadsheet '{info.get('spreadsheetTitle', 'Active Sheet')}'[/green]")
            console.print(f"    Webhook Status: {info.get('status', 'ok')} - {info.get('message', '')}")
        else:
            console.print("  [cyan]Testing Google Cloud Service Account...[/cyan]")
            sheets = GoogleSheetsClient(
                service_account_path=config.service_account_path,
                spreadsheet_id=config.spreadsheet_id,
                games_log_title=config.sheet_games_log_name,
                squares_tracker_title=config.sheet_squares_tracker_name,
            )
            sheets.initialize_sheets()
            console.print(f"  [green]✓ Connected successfully to Google Spreadsheet '{sheets.spreadsheet.title}'[/green]")
            console.print(f"    Target Tabs verified: '{config.sheet_games_log_name}', '{config.sheet_squares_tracker_name}'")
    except Exception as e:
        console.print(f"  [red]✗ Google Sheets check failed:[/red] {e}")

def cmd_create_board(args: argparse.Namespace) -> None:
    """Handles the 'create-board' command to setup the 10x10 Game Board tab."""
    console.print(Panel.fit("[bold cyan]🏀 Setting Up Sports Squares Game Board[/bold cyan]", title="Game Board Setup"))
    from src.sheets_client import create_sheets_client

    config.validate_sheets_config()
    client = create_sheets_client(config)

    console.print("Connecting to Google Sheets...")
    result = client.create_game_board(force=args.force)

    status = result.get("status", "unknown")
    msg = result.get("message", "")

    if status == "exists":
        console.print(f"\n[yellow]ℹ {msg}[/yellow]")
        console.print("[dim]Tip: If you want to randomize new numbers and reset the board, run with [bold]--force[/bold]:[/dim]")
        console.print("  [cyan].venv\\Scripts\\python main.py create-board --force[/cyan]")
        return

    home_digits = result.get("homeDigits", [])
    away_digits = result.get("awayDigits", [])

    console.print(f"\n[bold green]✓ {msg}[/bold green]")

    if home_digits and away_digits:
        # Display visual preview of the board in terminal
        table = Table(title="🏀 Sports Squares Game Board (Preview)", show_header=True, header_style="bold magenta")
        table.add_column("Away / Home", style="bold yellow", width=14)
        for h in home_digits:
            table.add_column(f"H: {h}", justify="center", style="bold cyan", width=6)

        for a in away_digits:
            row_cells = [f"A: {a}"] + ["·" for _ in range(10)]
            table.add_row(*row_cells)

        console.print(table)
        console.print(f"[bold]Home Team Digits (Top):[/bold]  {home_digits}")
        console.print(f"[bold]Away Team Digits (Left):[/bold] {away_digits}")
        console.print("\n[green]Tab 'game board' is configured with 10x10 squares, alternating shading, and borders.[/green]")
        console.print("[green]Tab 'Payouts' is also verified/created with 100-player capacity and automatic player formulas.[/green]")

def cmd_setup_payouts(args: argparse.Namespace) -> None:
    """Handles the 'setup-payouts' command to configure the Payouts tab."""
    console.print(Panel.fit("[bold cyan]💰 Setting Up Sports Squares Payouts Sheet[/bold cyan]", title="Payouts Sheet Setup"))
    from src.sheets_client import create_sheets_client

    config.validate_sheets_config()
    client = create_sheets_client(config)

    console.print("Connecting to Google Sheets...")
    result = client.create_payouts_sheet(force=args.force)

    status = result.get("status", "unknown")
    msg = result.get("message", "")

    if status == "exists":
        console.print(f"\n[yellow]ℹ {msg}[/yellow]")
        console.print("[dim]Tip: If you want to recreate the Payouts sheet, run with [bold]--force[/bold]:[/dim]")
        console.print("  [cyan].venv\\Scripts\\python main.py setup-payouts --force[/cyan]")
        return

    console.print(f"\n[bold green]✓ {msg}[/bold green]")
    console.print("[green]The 'Payouts' tab is configured with 100-player capacity, automatic unique player detection, square counts, cell coordinates, round winnings, and total payouts.[/green]")

def cmd_setup_guide(args: argparse.Namespace) -> None:
    """Displays instructions for Google Apps Script Webhook (Zero GCP setup)."""
    guide = (
        "[bold cyan]Zero Google Cloud Setup Guide (Google Apps Script Webhook)[/bold cyan]\n\n"
        "1. Open your Google Spreadsheet:\n"
        "   https://docs.google.com/spreadsheets/d/1oRC1NXID8JvBRqE5WUcjJWMNtv7AN5iCpEKQESLS6vo/edit\n\n"
        "2. Click [bold]Extensions > Apps Script[/bold] in the top toolbar.\n\n"
        "3. Replace any code in [bold]Code.gs[/bold] with the contents of [bold]google_apps_script.js[/bold].\n\n"
        "4. Click [bold]Deploy > New deployment[/bold] (top right):\n"
        "   • Select type: [green]Web app[/green]\n"
        "   • Description: [green]Sports Squares Sync & Game Board[/green]\n"
        "   • Execute as: [green]Me[/green]\n"
        "   • Who has access: [green]Anyone[/green]\n\n"
        "5. Click [bold]Deploy[/bold] (authorize when prompted).\n\n"
        "6. Copy the [bold]Web app URL[/bold] and paste it into your [bold].env[/bold] file:\n"
        "   [green]GOOGLE_WEBHOOK_URL=https://script.google.com/macros/s/.../exec[/green]\n"
    )
    console.print(Panel(guide, title="🏀 Sports Squares Setup Guide", border_style="cyan"))

def main():
    parser = argparse.ArgumentParser(
        description="Sports Squares: Fetch college basketball scores by period from ESPN (or api-sports.io) and inject into Google Sheets."
    )
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # Setup Guide Command
    p_guide = subparsers.add_parser("setup-guide", help="Show 1-minute Google Apps Script setup instructions (Zero GCP)")
    p_guide.set_defaults(func=cmd_setup_guide)

    # Create Game Board Command
    p_board = subparsers.add_parser("create-board", help="Create or configure the 10x10 'game board' tab on Google Sheets")
    p_board.add_argument("--force", action="store_true", help="Force regenerate unique random numbers even if board already exists")
    p_board.set_defaults(func=cmd_create_board)

    # Setup Payouts Command
    p_payouts = subparsers.add_parser("setup-payouts", help="Create or configure the 'Payouts' tab on Google Sheets")
    p_payouts.add_argument("--force", action="store_true", help="Recreate the Payouts tab even if it already exists")
    p_payouts.set_defaults(func=cmd_setup_payouts)

    # Fetch Command
    p_fetch = subparsers.add_parser("fetch", help="Fetch games for a date or full tournament and update Google Sheets")
    p_fetch.add_argument("--date", type=str, help="Date in YYYY-MM-DD or YYYYMMDD format (defaults to today)")
    p_fetch.add_argument("--year", type=int, help="Fetch all March Madness tournament games for a specific year (e.g. 2024)")
    p_fetch.add_argument("--tournament", "--march-madness", dest="tournament", action="store_true", help="Filter for only NCAA Tournament (March Madness) games")
    p_fetch.add_argument("--round", type=str, help="Filter for a specific tournament round (e.g. '1st Round', 'Sweet 16', 'Final Four', 'Championship')")
    p_fetch.add_argument("--gender", type=str, choices=["mens", "womens"], default="mens", help="NCAA Division: mens (default) or womens")
    p_fetch.add_argument("--source", type=str, choices=["espn", "api-sports"], default="espn", help="Data source: espn (default, free) or api-sports")
    p_fetch.add_argument("--league", type=int, help="League ID (if using api-sports source)")
    p_fetch.add_argument("--season", type=str, help="Season string (if using api-sports source)")
    p_fetch.add_argument("--live", action="store_true", help="Fetch only currently live games")
    p_fetch.add_argument("--mock", action="store_true", help="Use realistic sample data for local testing")
    p_fetch.add_argument("--dry-run", action="store_true", help="Fetch and print scores without updating Google Sheets")
    p_fetch.set_defaults(func=cmd_fetch)

    # Poll Command
    p_poll = subparsers.add_parser("poll", help="Continuously poll live games and update Google Sheets")
    p_poll.add_argument("--interval", type=int, help="Polling interval in seconds (default from .env: 60)")
    p_poll.add_argument("--tournament", "--march-madness", dest="tournament", action="store_true", help="Poll only active March Madness tournament games")
    p_poll.add_argument("--round", type=str, help="Filter for a specific tournament round")
    p_poll.add_argument("--gender", type=str, choices=["mens", "womens"], default="mens", help="NCAA Division: mens (default) or womens")
    p_poll.add_argument("--source", type=str, choices=["espn", "api-sports"], default="espn", help="Data source: espn (default, free) or api-sports")
    p_poll.add_argument("--league", type=int, help="League ID (if using api-sports source)")
    p_poll.add_argument("--season", type=str, help="Season string (if using api-sports source)")
    p_poll.add_argument("--mock", action="store_true", help="Use realistic sample data for local testing")
    p_poll.add_argument("--dry-run", action="store_true", help="Fetch and print scores without updating Google Sheets")
    p_poll.set_defaults(func=cmd_poll)

    # List Leagues Command (for api-sports)
    p_leagues = subparsers.add_parser("list-leagues", help="Search and list basketball league IDs (for api-sports)")
    p_leagues.add_argument("--search", type=str, default="NCAA", help="Search keyword (default: 'NCAA')")
    p_leagues.set_defaults(func=cmd_list_leagues)

    # Test Command
    p_test = subparsers.add_parser("test", help="Test credentials and API connectivity")
    p_test.set_defaults(func=cmd_test)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    try:
        args.func(args)
    except Exception as e:
        console.print(f"\n[bold red]Error:[/bold red] {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
