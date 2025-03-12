from src.console import console
import httpx
import json


async def search_tvmaze(filename, year, imdbID, tvdbID, manual_date=None, tvmaze_manual=None, debug=False, return_full_tuple=False):
    """Searches TVMaze for a show using TVDB ID, IMDb ID, or a title query.

    - If `return_full_tuple=True`, returns `(tvmaze_id, imdbID, tvdbID)`.
    - Otherwise, only returns `tvmaze_id`.
    """
    # Convert TVDB ID to integer
    try:
        tvdbID = int(tvdbID) if tvdbID not in (None, '', '0') else 0
    except ValueError:
        console.print(f"[red]Error: tvdbID is not a valid integer. Received: {tvdbID}[/red]")
        tvdbID = 0

    # Handle IMDb ID - ensure it's an integer without tt prefix
    try:
        if isinstance(imdbID, str) and imdbID.startswith('tt'):
            imdbID = int(imdbID[2:])
        else:
            imdbID = int(imdbID) if imdbID not in (None, '', '0') else 0
    except ValueError:
        console.print(f"[red]Error: imdbID is not a valid integer. Received: {imdbID}[/red]")
        imdbID = 0

    # If manual selection has been provided, return it directly
    if tvmaze_manual:
        try:
            tvmaze_id = int(tvmaze_manual)
            return (tvmaze_id, imdbID, tvdbID) if return_full_tuple else tvmaze_id
        except (ValueError, TypeError):
            console.print(f"[red]Error: tvmaze_manual is not a valid integer. Received: {tvmaze_manual}[/red]")
            tvmaze_id = 0
            return (tvmaze_id, imdbID, tvdbID) if return_full_tuple else tvmaze_id

    tvmaze_id = 0
    results = []

    async def fetch_tvmaze_data(url, params):
        """Helper function to fetch data from TVMaze API."""
        response = await _make_tvmaze_request(url, params)
        if response:
            return [response] if isinstance(response, dict) else response
        return []

    # Primary search logic
    if manual_date is None:
        if tvdbID:
            results.extend(await fetch_tvmaze_data("https://api.tvmaze.com/lookup/shows", {"thetvdb": tvdbID}))

        if not results and imdbID:
            results.extend(await fetch_tvmaze_data("https://api.tvmaze.com/lookup/shows", {"imdb": f"tt{imdbID:07d}"}))

        if not results:
            search_resp = await fetch_tvmaze_data("https://api.tvmaze.com/search/shows", {"q": filename})
            results.extend([each['show'] for each in search_resp if 'show' in each])
    else:
        if tvdbID:
            results.extend(await fetch_tvmaze_data("https://api.tvmaze.com/lookup/shows", {"thetvdb": tvdbID}))

        if imdbID:
            results.extend(await fetch_tvmaze_data("https://api.tvmaze.com/lookup/shows", {"imdb": f"tt{imdbID:07d}"}))

        search_resp = await fetch_tvmaze_data("https://api.tvmaze.com/search/shows", {"q": filename})
        results.extend([each['show'] for each in search_resp if 'show' in each])

    # Deduplicate results by TVMaze ID
    seen = set()
    unique_results = [show for show in results if show['id'] not in seen and not seen.add(show['id'])]

    if not unique_results:
        if debug:
            console.print("[yellow]No TVMaze results found.[/yellow]")
        return (tvmaze_id, imdbID, tvdbID) if return_full_tuple else tvmaze_id

    # Manual selection process
    if manual_date is not None:
        console.print("[bold]Search results:[/bold]")
        for idx, show in enumerate(unique_results):
            console.print(f"[bold red]{idx + 1}[/bold red]. [green]{show.get('name', 'Unknown')} (TVmaze ID:[/green] [bold red]{show['id']}[/bold red])")
            console.print(f"[yellow]   Premiered: {show.get('premiered', 'Unknown')}[/yellow]")
            console.print(f"   Externals: {json.dumps(show.get('externals', {}), indent=2)}")

        while True:
            try:
                choice = int(input(f"Enter the number of the correct show (1-{len(unique_results)}) or 0 to skip: "))
                if choice == 0:
                    console.print("Skipping selection.")
                    break
                if 1 <= choice <= len(unique_results):
                    selected_show = unique_results[choice - 1]
                    tvmaze_id = int(selected_show['id'])
                    console.print(f"Selected show: {selected_show.get('name')} (TVmaze ID: {tvmaze_id})")
                    break
                else:
                    console.print(f"Invalid choice. Please choose a number between 1 and {len(unique_results)}, or 0 to skip.")
            except ValueError:
                console.print("Invalid input. Please enter a number.")
    else:
        selected_show = unique_results[0]
        tvmaze_id = int(selected_show['id'])
        if debug:
            console.print(f"[cyan]Automatically selected show: {selected_show.get('name')} (TVmaze ID: {tvmaze_id})[/cyan]")

    if debug:
        console.print(f"[cyan]Returning TVmaze ID: {tvmaze_id} (type: {type(tvmaze_id).__name__}), IMDb ID: {imdbID} (type: {type(imdbID).__name__}), TVDB ID: {tvdbID} (type: {type(tvdbID).__name__})[/cyan]")

    return (tvmaze_id, imdbID, tvdbID) if return_full_tuple else tvmaze_id


async def _make_tvmaze_request(url, params):
    """Sync function to make the request inside ThreadPoolExecutor."""
    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            resp = await client.get(url, params=params, timeout=10)
            if resp.status_code == 200:
                return resp.json()
            else:
                return None
    except httpx.HTTPStatusError as e:
        print(f"[ERROR] TVmaze API error: {e.response.status_code}")
    except httpx.RequestError as e:
        print(f"[ERROR] Network error while accessing TVmaze: {e}")
    return {}
