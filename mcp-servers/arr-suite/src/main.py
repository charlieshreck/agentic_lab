#!/usr/bin/env python3
"""Arr Suite MCP server for Sonarr, Radarr, and Prowlarr management."""
import os
import logging
import httpx
from typing import List, Optional
from fastmcp import FastMCP
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
SONARR_URL = os.environ.get("SONARR_URL", "http://sonarr:8989")
SONARR_API_KEY = os.environ.get("SONARR_API_KEY", "")
RADARR_URL = os.environ.get("RADARR_URL", "http://radarr:7878")
RADARR_API_KEY = os.environ.get("RADARR_API_KEY", "")
PROWLARR_URL = os.environ.get("PROWLARR_URL", "http://prowlarr:9696")
PROWLARR_API_KEY = os.environ.get("PROWLARR_API_KEY", "")

mcp = FastMCP(
    name="arr-suite-mcp",
    instructions="""
    MCP server for media management with Sonarr, Radarr, and Prowlarr.
    Provides tools to manage TV shows, movies, and indexers.
    Use search tools to find content, add tools to request downloads.
    """
)


class MediaItem(BaseModel):
    id: int
    title: str
    year: Optional[int]
    status: str
    monitored: bool
    size_on_disk: int


class QueueItem(BaseModel):
    id: int
    title: str
    status: str
    progress: float
    type: str  # tv or movie


class SearchResult(BaseModel):
    id: int
    title: str
    year: Optional[int]
    overview: str


async def arr_request(
    base_url: str,
    api_key: str,
    endpoint: str,
    method: str = "GET",
    data: dict = None,
    timeout: float = 30.0
) -> dict:
    """Make request to *arr API."""
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.request(
            method,
            f"{base_url}/api/v3/{endpoint}",
            headers={"X-Api-Key": api_key},
            json=data
        )
        response.raise_for_status()
        return response.json() if response.content else {}


@mcp.resource("health://status")
def health_check() -> str:
    """Health check endpoint."""
    return "healthy"


# ===== SONARR TOOLS =====

@mcp.tool()
async def list_tv_shows(monitored_only: bool = True) -> List[MediaItem]:
    """
    List all TV shows in Sonarr.

    Args:
        monitored_only: Only return monitored shows (default: True)

    Returns:
        List of TV show information
    """
    try:
        shows = await arr_request(SONARR_URL, SONARR_API_KEY, "series")
        result = []
        for s in shows:
            if not monitored_only or s["monitored"]:
                result.append(MediaItem(
                    id=s["id"],
                    title=s["title"],
                    year=s.get("year"),
                    status=s["status"],
                    monitored=s["monitored"],
                    size_on_disk=s.get("statistics", {}).get("sizeOnDisk", 0)
                ))
        return result
    except Exception as e:
        logger.error(f"Failed to list TV shows: {e}")
        return []


@mcp.tool()
async def search_tv_show(query: str) -> List[SearchResult]:
    """
    Search for a TV show to add to Sonarr.

    Args:
        query: Search term (show name)

    Returns:
        List of matching shows from TVDB
    """
    try:
        results = await arr_request(
            SONARR_URL, SONARR_API_KEY,
            f"series/lookup?term={query}"
        )
        return [
            SearchResult(
                id=r.get("tvdbId", 0),
                title=r["title"],
                year=r.get("year"),
                overview=r.get("overview", "")[:300]
            )
            for r in results[:5]
        ]
    except Exception as e:
        logger.error(f"Failed to search TV shows: {e}")
        return []


@mcp.tool()
async def trigger_show_search(series_id: int) -> str:
    """
    Trigger a search for missing episodes of a TV show.

    Args:
        series_id: Sonarr series ID

    Returns:
        Status message
    """
    try:
        await arr_request(
            SONARR_URL, SONARR_API_KEY,
            "command",
            method="POST",
            data={"name": "SeriesSearch", "seriesId": series_id}
        )
        return f"Triggered search for series {series_id}"
    except Exception as e:
        logger.error(f"Failed to trigger show search: {e}")
        return f"Error: {str(e)}"


@mcp.tool()
async def get_sonarr_calendar(days: int = 7) -> List[dict]:
    """
    Get upcoming TV episodes from Sonarr calendar.

    Args:
        days: Number of days to look ahead (default: 7)

    Returns:
        List of upcoming episodes
    """
    try:
        from datetime import datetime, timedelta
        start = datetime.now().strftime("%Y-%m-%d")
        end = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")

        episodes = await arr_request(
            SONARR_URL, SONARR_API_KEY,
            f"calendar?start={start}&end={end}"
        )
        return [
            {
                "series": ep.get("series", {}).get("title", "Unknown"),
                "title": ep.get("title", "TBA"),
                "season": ep.get("seasonNumber"),
                "episode": ep.get("episodeNumber"),
                "air_date": ep.get("airDate")
            }
            for ep in episodes
        ]
    except Exception as e:
        logger.error(f"Failed to get Sonarr calendar: {e}")
        return []


# ===== RADARR TOOLS =====

@mcp.tool()
async def list_movies(monitored_only: bool = True) -> List[MediaItem]:
    """
    List all movies in Radarr.

    Args:
        monitored_only: Only return monitored movies (default: True)

    Returns:
        List of movie information
    """
    try:
        movies = await arr_request(RADARR_URL, RADARR_API_KEY, "movie")
        result = []
        for m in movies:
            if not monitored_only or m["monitored"]:
                result.append(MediaItem(
                    id=m["id"],
                    title=m["title"],
                    year=m.get("year"),
                    status="downloaded" if m.get("hasFile") else "missing",
                    monitored=m["monitored"],
                    size_on_disk=m.get("sizeOnDisk", 0)
                ))
        return result
    except Exception as e:
        logger.error(f"Failed to list movies: {e}")
        return []


@mcp.tool()
async def search_movie(query: str) -> List[SearchResult]:
    """
    Search for a movie to add to Radarr.

    Args:
        query: Search term (movie name)

    Returns:
        List of matching movies from TMDB
    """
    try:
        results = await arr_request(
            RADARR_URL, RADARR_API_KEY,
            f"movie/lookup?term={query}"
        )
        return [
            SearchResult(
                id=r.get("tmdbId", 0),
                title=r["title"],
                year=r.get("year"),
                overview=r.get("overview", "")[:300]
            )
            for r in results[:5]
        ]
    except Exception as e:
        logger.error(f"Failed to search movies: {e}")
        return []


@mcp.tool()
async def add_movie(
    tmdb_id: int,
    quality_profile_id: int = 1,
    root_folder_path: str = "/movies"
) -> str:
    """
    Add a movie to Radarr for download.

    Args:
        tmdb_id: TMDB ID from search results
        quality_profile_id: Quality profile (1=Any, adjust as needed)
        root_folder_path: Where to store the movie

    Returns:
        Status message
    """
    try:
        # Lookup movie details
        movie_data = await arr_request(
            RADARR_URL, RADARR_API_KEY,
            f"movie/lookup/tmdb?tmdbId={tmdb_id}"
        )

        movie_data["qualityProfileId"] = quality_profile_id
        movie_data["rootFolderPath"] = root_folder_path
        movie_data["monitored"] = True
        movie_data["addOptions"] = {"searchForMovie": True}

        await arr_request(
            RADARR_URL, RADARR_API_KEY,
            "movie",
            method="POST",
            data=movie_data
        )
        return f"Added movie: {movie_data.get('title', 'Unknown')}"
    except Exception as e:
        logger.error(f"Failed to add movie: {e}")
        return f"Error: {str(e)}"


@mcp.tool()
async def trigger_movie_search(movie_id: int) -> str:
    """
    Trigger a search for a movie in Radarr.

    Args:
        movie_id: Radarr movie ID

    Returns:
        Status message
    """
    try:
        await arr_request(
            RADARR_URL, RADARR_API_KEY,
            "command",
            method="POST",
            data={"name": "MoviesSearch", "movieIds": [movie_id]}
        )
        return f"Triggered search for movie {movie_id}"
    except Exception as e:
        logger.error(f"Failed to trigger movie search: {e}")
        return f"Error: {str(e)}"


# ===== COMBINED TOOLS =====

@mcp.tool()
async def get_download_queue() -> List[QueueItem]:
    """
    Get current download queue from both Sonarr and Radarr.

    Returns:
        Combined list of downloading items
    """
    combined = []

    try:
        sonarr_queue = await arr_request(SONARR_URL, SONARR_API_KEY, "queue")
        for item in sonarr_queue.get("records", []):
            size = item.get("size", 1)
            sizeleft = item.get("sizeleft", 0)
            progress = ((size - sizeleft) / size * 100) if size > 0 else 0
            combined.append(QueueItem(
                id=item.get("id", 0),
                title=item.get("title", "Unknown"),
                status=item.get("status", "unknown"),
                progress=round(progress, 1),
                type="tv"
            ))
    except Exception as e:
        logger.error(f"Failed to get Sonarr queue: {e}")

    try:
        radarr_queue = await arr_request(RADARR_URL, RADARR_API_KEY, "queue")
        for item in radarr_queue.get("records", []):
            size = item.get("size", 1)
            sizeleft = item.get("sizeleft", 0)
            progress = ((size - sizeleft) / size * 100) if size > 0 else 0
            combined.append(QueueItem(
                id=item.get("id", 0),
                title=item.get("title", "Unknown"),
                status=item.get("status", "unknown"),
                progress=round(progress, 1),
                type="movie"
            ))
    except Exception as e:
        logger.error(f"Failed to get Radarr queue: {e}")

    return combined


@mcp.tool()
async def get_system_status() -> dict:
    """
    Get system status from all arr services.

    Returns:
        Status of Sonarr, Radarr, and Prowlarr
    """
    status = {}

    for name, url, key in [
        ("sonarr", SONARR_URL, SONARR_API_KEY),
        ("radarr", RADARR_URL, RADARR_API_KEY),
        ("prowlarr", PROWLARR_URL, PROWLARR_API_KEY)
    ]:
        try:
            info = await arr_request(url, key, "system/status")
            status[name] = {
                "version": info.get("version", "unknown"),
                "branch": info.get("branch", "unknown"),
                "status": "online"
            }
        except Exception as e:
            status[name] = {"status": "offline", "error": str(e)}

    return status


# ===== PROWLARR TOOLS =====

@mcp.tool()
async def list_indexers() -> List[dict]:
    """
    List all configured indexers in Prowlarr.

    Returns:
        List of indexer status
    """
    try:
        indexers = await arr_request(PROWLARR_URL, PROWLARR_API_KEY, "indexer")
        return [
            {
                "id": idx["id"],
                "name": idx["name"],
                "protocol": idx.get("protocol", "unknown"),
                "enable": idx.get("enable", False),
                "priority": idx.get("priority", 50)
            }
            for idx in indexers
        ]
    except Exception as e:
        logger.error(f"Failed to list indexers: {e}")
        return []


@mcp.tool()
async def test_indexer(indexer_id: int) -> str:
    """
    Test connectivity to an indexer.

    Args:
        indexer_id: Prowlarr indexer ID

    Returns:
        Test result message
    """
    try:
        await arr_request(
            PROWLARR_URL, PROWLARR_API_KEY,
            f"indexer/{indexer_id}/test",
            method="POST"
        )
        return f"Indexer {indexer_id} test passed"
    except Exception as e:
        logger.error(f"Failed to test indexer: {e}")
        return f"Error: {str(e)}"


def main():
    port = int(os.environ.get("PORT", "8000"))
    transport = os.environ.get("MCP_TRANSPORT", "sse")

    logger.info(f"Starting arr-suite MCP server on port {port} with {transport} transport")

    if transport == "http":
        from starlette.middleware.cors import CORSMiddleware
        app = mcp.streamable_http_app()
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["GET", "POST", "OPTIONS"],
            allow_headers=["*"],
        )
        import uvicorn
        uvicorn.run(app, host="0.0.0.0", port=port)
    else:
        mcp.run(transport="sse", host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
