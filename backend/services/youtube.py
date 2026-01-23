"""
YouTube transcript and search service for dbAI Pulse.
Fetches and processes fantasy football video transcripts.
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import NoTranscriptFound, TranscriptsDisabled

from config import get_settings

logger = logging.getLogger(__name__)


class YouTubeService:
    """Service for searching YouTube and fetching video transcripts."""

    # Curated fantasy football channels: handle -> display name
    # Handles will be resolved to channel IDs on first use and cached
    CURATED_HANDLES = {
        "thefantasyfootballers": "The Fantasy Footballers",
        "fantasypros": "FantasyPros",
        "fantasyfootballtoday": "Fantasy Football Today (CBS)",
        "lateroundff": "Late-Round Fantasy Football",
    }

    # Cache for search results: key -> (results, timestamp)
    _search_cache: Dict[str, Tuple[List[Dict], float]] = {}

    # Cache for resolved channel IDs: handle -> channel_id
    _channel_id_cache: Dict[str, str] = {}

    def __init__(self):
        self.settings = get_settings()
        self._youtube = None

    @property
    def youtube(self):
        """Lazy-load YouTube API client."""
        if self._youtube is None and self.settings.youtube_api_key:
            try:
                from googleapiclient.discovery import build

                self._youtube = build(
                    "youtube", "v3", developerKey=self.settings.youtube_api_key
                )
                logger.info("YouTube API client initialized")
            except Exception as e:
                logger.error(f"Failed to initialize YouTube API client: {e}")
        return self._youtube

    def _resolve_handle_to_channel_id(self, handle: str) -> Optional[str]:
        """
        Resolve a YouTube handle to channel ID.
        Results are cached permanently to avoid repeated API calls.
        """
        # Check cache first
        if handle in self._channel_id_cache:
            return self._channel_id_cache[handle]

        if not self.youtube:
            return None

        try:
            # Search for the channel by handle
            request = self.youtube.search().list(
                part="id,snippet",
                q=handle,
                type="channel",
                maxResults=1,
            )
            response = request.execute()

            if response.get("items"):
                channel_id = response["items"][0]["id"]["channelId"]
                self._channel_id_cache[handle] = channel_id
                logger.info(f"Resolved handle @{handle} to channel ID {channel_id}")
                return channel_id

        except Exception as e:
            logger.warning(f"Failed to resolve handle @{handle}: {e}")

        return None

    def search_videos(
        self,
        player_name: str,
        max_results: int = 5,
        days_back: int = 90,  # Default 90 days to cover offseason testing
    ) -> List[Dict]:
        """
        Search YouTube for fantasy football videos mentioning a player.
        First searches curated channels, then falls back to general search.

        Args:
            player_name: Player name to search for
            max_results: Maximum number of videos to return
            days_back: Only include videos from the last N days

        Returns:
            List of video metadata dicts with keys:
            - video_id, title, channel_name, published_at, url, is_curated
        """
        # Check cache first
        cache_key = f"{player_name}:{max_results}:{days_back}"
        if cache_key in self._search_cache:
            results, timestamp = self._search_cache[cache_key]
            if time.time() - timestamp < self.settings.transcript_cache_ttl:
                logger.info(f"Returning cached search results for '{player_name}'")
                return results

        if not self.youtube:
            logger.warning("YouTube API key not configured, skipping video search")
            return []

        # Calculate date filter (ISO 8601 format)
        published_after = (datetime.utcnow() - timedelta(days=days_back)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )

        all_results = []
        curated_channel_names = set()

        # Step 1: Search curated channels first
        for handle, channel_name in self.CURATED_HANDLES.items():
            try:
                # Resolve handle to channel ID
                channel_id = self._resolve_handle_to_channel_id(handle)
                if not channel_id:
                    logger.warning(f"Could not resolve channel @{handle}, skipping")
                    continue

                # Search within this specific channel
                request = self.youtube.search().list(
                    part="snippet",
                    channelId=channel_id,
                    q=f"{player_name} fantasy football",
                    type="video",
                    maxResults=2,  # 2 videos per curated channel
                    order="date",
                    publishedAfter=published_after,
                )
                response = request.execute()

                for item in response.get("items", []):
                    video_id = item["id"]["videoId"]
                    snippet = item["snippet"]
                    all_results.append(
                        {
                            "video_id": video_id,
                            "title": snippet["title"],
                            "channel_name": channel_name,
                            "published_at": snippet["publishedAt"],
                            "url": f"https://www.youtube.com/watch?v={video_id}",
                            "is_curated": True,
                        }
                    )
                    curated_channel_names.add(channel_name)

                logger.info(
                    f"Found {len(response.get('items', []))} videos for "
                    f"'{player_name}' in @{handle}"
                )

            except Exception as e:
                logger.warning(f"Error searching channel @{handle}: {e}")
                continue

        # Step 2: Fall back to general search if not enough results
        if len(all_results) < max_results:
            try:
                remaining = max_results - len(all_results)
                request = self.youtube.search().list(
                    part="snippet",
                    q=f"{player_name} fantasy football analysis",
                    type="video",
                    maxResults=remaining + 5,  # Get extra to filter duplicates
                    order="relevance",
                    publishedAfter=published_after,
                )
                response = request.execute()

                for item in response.get("items", []):
                    video_id = item["id"]["videoId"]
                    snippet = item["snippet"]
                    channel_title = snippet["channelTitle"]

                    # Skip if we already have this video or from same channel
                    if any(r["video_id"] == video_id for r in all_results):
                        continue
                    if channel_title in curated_channel_names:
                        continue

                    all_results.append(
                        {
                            "video_id": video_id,
                            "title": snippet["title"],
                            "channel_name": channel_title,
                            "published_at": snippet["publishedAt"],
                            "url": f"https://www.youtube.com/watch?v={video_id}",
                            "is_curated": False,
                        }
                    )

                    if len(all_results) >= max_results:
                        break

                logger.info(
                    f"Added general search results for '{player_name}', "
                    f"total now: {len(all_results)}"
                )

            except Exception as e:
                logger.warning(f"Error in general YouTube search: {e}")

        # Sort: curated first (by date), then general (by date)
        curated = [r for r in all_results if r.get("is_curated")]
        general = [r for r in all_results if not r.get("is_curated")]
        curated.sort(key=lambda x: x["published_at"], reverse=True)
        general.sort(key=lambda x: x["published_at"], reverse=True)
        results = (curated + general)[:max_results]

        # Cache results
        self._search_cache[cache_key] = (results, time.time())

        logger.info(
            f"Returning {len(results)} total videos for '{player_name}' "
            f"({len(curated)} curated, {len(general)} general)"
        )
        return results

    @staticmethod
    def get_transcript(video_id: str) -> Optional[str]:
        """
        Fetch transcript for a YouTube video.

        Args:
            video_id: YouTube video ID

        Returns:
            Combined transcript text or None if unavailable
        """
        try:
            # youtube-transcript-api 1.x uses instance-based API
            ytt_api = YouTubeTranscriptApi()
            transcript_list = ytt_api.fetch(video_id)

            # Combine all transcript segments
            full_text = " ".join([entry.text for entry in transcript_list])

            logger.info(
                f"Fetched transcript for video {video_id}, length: {len(full_text)} chars"
            )
            return full_text

        except (TranscriptsDisabled, NoTranscriptFound) as e:
            logger.warning(f"Transcript not available for video {video_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error fetching transcript for video {video_id}: {e}")
            return None

    @staticmethod
    def extract_player_mentions(
        transcript: str, player_name: str, context_chars: int = 750
    ) -> List[Dict[str, str]]:
        """
        Extract segments of transcript that mention the player.

        Args:
            transcript: Full transcript text
            player_name: Player name to search for (e.g., "Josh Allen")
            context_chars: Characters to include before/after mention

        Returns:
            List of relevant transcript segments
        """
        if not transcript:
            return []

        mentions = []
        transcript_lower = transcript.lower()
        player_lower = player_name.lower()

        # Also search for last name only for common references
        name_parts = player_name.split()
        search_terms = [player_lower]
        if len(name_parts) > 1:
            search_terms.append(name_parts[-1].lower())  # Last name

        found_positions = set()

        for term in search_terms:
            start_pos = 0
            while True:
                pos = transcript_lower.find(term, start_pos)
                if pos == -1:
                    break

                # Avoid duplicate overlapping mentions
                if any(abs(pos - fp) < context_chars // 2 for fp in found_positions):
                    start_pos = pos + len(term)
                    continue

                found_positions.add(pos)

                # Extract context around mention
                context_start = max(0, pos - context_chars)
                context_end = min(
                    len(transcript), pos + len(player_name) + context_chars
                )

                segment = transcript[context_start:context_end].strip()

                mentions.append({"text": segment, "position": pos})

                start_pos = pos + len(term)

        # Sort by position and limit to avoid overwhelming context
        mentions.sort(key=lambda x: x["position"])
        mentions = mentions[:5]  # Max 5 mentions per video

        logger.info(f"Found {len(mentions)} mentions of '{player_name}' in transcript")
        return mentions

    @staticmethod
    def summarize_for_gemini(
        mentions: List[Dict[str, str]], max_length: int = 2000
    ) -> str:
        """
        Combine and truncate player mentions for Gemini input.

        Args:
            mentions: List of transcript segments
            max_length: Maximum combined length

        Returns:
            Summarized text ready for Gemini
        """
        if not mentions:
            return "No specific mentions found in transcripts."

        combined = "\n\n---\n\n".join([m["text"] for m in mentions])

        if len(combined) > max_length:
            combined = combined[:max_length] + "...[truncated]"

        return combined


# Singleton instance
_youtube_service: Optional[YouTubeService] = None


def get_youtube_service() -> YouTubeService:
    """Get YouTube service singleton instance."""
    global _youtube_service
    if _youtube_service is None:
        _youtube_service = YouTubeService()
    return _youtube_service
