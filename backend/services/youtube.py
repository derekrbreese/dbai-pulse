"""
YouTube transcript service for dbAI Pulse.
Fetches and processes fantasy football video transcripts.
"""

import logging
from typing import List, Dict, Optional
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound

from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class YouTubeService:
    """Service for fetching YouTube video transcripts."""

    # Popular fantasy football channels (add more as needed)
    FANTASY_CHANNELS = [
        "TheFantasyFootballers",
        "LateRoundQB",
        "FantasyPros",
        "CBSSportsFantasy",
    ]

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
            transcript_list = YouTubeTranscriptApi.get_transcript(video_id)

            # Combine all transcript segments
            full_text = " ".join([entry["text"] for entry in transcript_list])

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
        transcript: str, player_name: str, context_chars: int = 500
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

        # Find all occurrences
        start_pos = 0
        while True:
            pos = transcript_lower.find(player_lower, start_pos)
            if pos == -1:
                break

            # Extract context around mention
            context_start = max(0, pos - context_chars)
            context_end = min(len(transcript), pos + len(player_name) + context_chars)

            segment = transcript[context_start:context_end].strip()

            mentions.append({"text": segment, "position": pos})

            start_pos = pos + len(player_name)

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


def get_youtube_service() -> YouTubeService:
    """Get YouTube service instance."""
    return YouTubeService()
