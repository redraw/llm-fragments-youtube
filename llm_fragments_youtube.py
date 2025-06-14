from typing import Optional
import llm
import os
import re
import subprocess
import tempfile
from urllib.parse import parse_qs, urlparse


@llm.hookimpl
def register_fragment_loaders(register):
    register("youtube", youtube_loader)
    register("yt", youtube_loader)


def youtube_loader(argument: str) -> llm.Fragment:
    """
    Load YouTube video subtitles as a fragment

    Argument is a YouTube URL or video ID, optionally with a language prefix
    Format: [lang:]url-or-id where lang is optional and defaults to 'en'

    Examples:
    - youtube:dQw4w9WgXcQ
    - youtube:https://www.youtube.com/watch?v=dQw4w9WgXcQ
    - youtube:en:dQw4w9WgXcQ
    - youtube:es:https://www.youtube.com/watch?v=dQw4w9WgXcQ
    """
    # Parse the argument to extract video ID and language
    video_id, language = _parse_argument(argument)

    # Create a temporary directory to store the subtitle file
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            # Construct the yt-dlp command
            cmd = [
                "yt-dlp",
                "--skip-download",
                "--write-sub",
                "--sub-format",
                "vtt",
                "-o",
                f"{temp_dir}/%(id)s.%(ext)s",
            ]

            # Add language parameter if specified
            if language:
                cmd.extend(["--sub-lang", language])
            else:
                # Default to English if no language specified
                cmd.extend(["--sub-lang", "en"])

            # Add the video URL
            cmd.append(f"https://www.youtube.com/watch?v={video_id}")

            # Run yt-dlp to download subtitles
            result = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True,
            )

            # Find the subtitle file
            subtitle_files = [
                os.path.join(temp_dir, f)
                for f in os.listdir(temp_dir)
                if f.endswith(".vtt")
            ]

            if not subtitle_files:
                # Check if auto-generated subtitles are available
                cmd = [
                    "yt-dlp",
                    "--skip-download",
                    "--write-auto-sub",
                    "--sub-format",
                    "vtt",
                    "-o",
                    f"{temp_dir}/%(id)s.%(ext)s",
                ]

                if language:
                    cmd.extend(["--sub-lang", language])
                else:
                    cmd.extend(["--sub-lang", "en"])

                cmd.append(f"https://www.youtube.com/watch?v={video_id}")

                # Run yt-dlp again for auto-generated subtitles
                result = subprocess.run(
                    cmd,
                    check=True,
                    capture_output=True,
                    text=True,
                )

                subtitle_files = [
                    os.path.join(temp_dir, f)
                    for f in os.listdir(temp_dir)
                    if f.endswith(".vtt")
                ]

            if not subtitle_files:
                raise ValueError(
                    f"No subtitles found for video {video_id}"
                    + (f" in language {language}" if language else "")
                )

            # Read the subtitle file
            subtitle_content = ""
            with open(subtitle_files[0], "r", encoding="utf-8") as f:
                subtitle_content = f.read()

            # Clean up the VTT format to make it more readable
            subtitle_content = _clean_vtt_content(subtitle_content)

            # Create the source URL
            source_url = f"https://www.youtube.com/watch?v={video_id}"
            if language:
                source_url += f"&cc_lang_pref={language}"

            # Return the fragment
            return llm.Fragment(
                content=subtitle_content,
                source=source_url,
            )

        except subprocess.CalledProcessError as e:
            # Handle yt-dlp errors
            error_message = e.stderr if e.stderr else str(e)
            raise ValueError(f"Failed to download subtitles: {error_message}")
        except Exception as e:
            # Handle other errors
            raise ValueError(f"Error processing YouTube video: {str(e)}")


def _parse_argument(argument: str) -> tuple[str, Optional[str]]:
    """
    Parse the argument to extract video ID and language
    Returns (video_id, language)

    Format: [lang:]url-or-id
    Examples:
    - dQw4w9WgXcQ
    - en:dQw4w9WgXcQ
    - es:https://www.youtube.com/watch?v=dQw4w9WgXcQ
    """
    # Check if language is specified in the format "lang:url-or-id"
    language = None
    if ":" in argument and not argument.startswith("http"):
        parts = argument.split(":", 1)
        language = parts[0]
        argument = parts[1]

    # Parse the URL or video ID
    parsed_url = urlparse(argument)
    query_params = parse_qs(parsed_url.query)

    # Extract video ID
    if parsed_url.netloc in ("www.youtube.com", "youtube.com"):
        # Handle youtube.com URLs
        if "v" in query_params:
            video_id = query_params["v"][0]
        else:
            raise ValueError(f"Invalid YouTube URL: {argument}")
    elif parsed_url.netloc == "youtu.be":
        # Handle youtu.be URLs
        video_id = parsed_url.path.lstrip("/").split("?")[0]
    elif parsed_url.netloc:
        # Any other domain
        raise ValueError(f"Invalid YouTube URL: {argument}")
    else:
        # Assume the argument is a video ID without query parameters
        video_id = parsed_url.path.split("?")[0]

    return video_id, language


def _clean_vtt_content(content: str) -> str:
    """
    Clean up the VTT subtitle content to make it more readable
    - Removes duplicate entries (YouTube subs often have ~3 duplicates per line)
    - Preserves timestamps every minute for time context
    - Removes HTML-like tags
    """
    # Direct parsing approach for all VTT files
    lines = content.split("\n")
    cleaned_lines = []
    prev_text = None  # Only keep track of the previous text
    last_minute_recorded = -1
    current_timestamp = None

    i = 0
    while i < len(lines):
        line = lines[i].strip()

        # Skip empty lines, headers, and metadata
        if (
            not line
            or line.startswith("WEBVTT")
            or line.startswith("Kind:")
            or line.startswith("Language:")
        ):
            i += 1
            continue

        # Process timestamp lines
        if "-->" in line:
            # Extract the start timestamp
            timestamp_match = re.match(r"(\d{2}:\d{2}:\d{2})", line)
            if timestamp_match:
                current_timestamp = timestamp_match.group(1)
                current_minute = int(current_timestamp.split(":")[1])

                # Add timestamp every minute
                if current_minute != last_minute_recorded:
                    cleaned_lines.append(f"[{current_timestamp}]")
                    last_minute_recorded = current_minute

            i += 1
            continue

        # Skip numeric cue identifiers
        if line.isdigit():
            i += 1
            continue

        # Process text lines
        if line:
            # Remove HTML-like tags and timestamps
            clean_line = re.sub(r"<[^>]+>", "", line)

            # Only add if not a duplicate of the previous line
            if clean_line.strip() and clean_line != prev_text:
                cleaned_lines.append(clean_line)
                prev_text = clean_line

        i += 1

    return "\n".join(cleaned_lines)
