import os
import tempfile
from pathlib import Path
from unittest import mock

import pytest
import llm
from llm_fragments_youtube import (
    youtube_loader,
    _parse_argument,
    _clean_vtt_content,
    register_fragment_loaders,
)


def test_register_fragment_loaders():
    """Test that the fragment loader is registered correctly."""
    mock_register = mock.Mock()
    register_fragment_loaders(mock_register)
    mock_register.assert_called_once_with("youtube", youtube_loader)


def test_parse_argument_video_id():
    """Test parsing a simple video ID."""
    video_id, language = _parse_argument("dQw4w9WgXcQ")
    assert video_id == "dQw4w9WgXcQ"
    assert language is None


def test_parse_argument_video_id_with_language():
    """Test parsing a video ID with language prefix."""
    video_id, language = _parse_argument("es:dQw4w9WgXcQ")
    assert video_id == "dQw4w9WgXcQ"
    assert language == "es"


def test_parse_argument_youtube_url():
    """Test parsing a full YouTube URL."""
    video_id, language = _parse_argument("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    assert video_id == "dQw4w9WgXcQ"
    assert language is None


def test_parse_argument_youtube_url_with_language():
    """Test parsing a YouTube URL with language prefix."""
    video_id, language = _parse_argument("es:https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    assert video_id == "dQw4w9WgXcQ"
    assert language == "es"


def test_parse_argument_youtu_be_url():
    """Test parsing a youtu.be short URL."""
    video_id, language = _parse_argument("https://youtu.be/dQw4w9WgXcQ")
    assert video_id == "dQw4w9WgXcQ"
    assert language is None


def test_parse_argument_youtu_be_url_with_language():
    """Test parsing a youtu.be URL with language prefix."""
    video_id, language = _parse_argument("es:https://youtu.be/dQw4w9WgXcQ")
    assert video_id == "dQw4w9WgXcQ"
    assert language == "es"


def test_parse_argument_youtube_url_with_cc_lang_pref():
    """Test parsing a YouTube URL with language prefix."""
    video_id, language = _parse_argument("es:https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    assert video_id == "dQw4w9WgXcQ"
    assert language == "es"


def test_parse_argument_invalid_url():
    """Test parsing an invalid URL."""
    with pytest.raises(ValueError):
        _parse_argument("https://example.com/video")


def test_clean_vtt_content():
    """Test cleaning VTT content."""
    vtt_content = """WEBVTT

1
00:00:00.000 --> 00:00:03.000
This is the first subtitle

2
00:00:04.000 --> 00:00:07.000
This is the second <b>subtitle</b>

3
00:00:08.000 --> 00:00:11.000
This is the third subtitle"""

    # Clean the content
    clean_content = _clean_vtt_content(vtt_content)
    
    # Check that HTML tags are removed
    assert "<b>" not in clean_content
    assert "</b>" not in clean_content
    
    # Check that all subtitle text is present
    assert "This is the first subtitle" in clean_content
    assert "This is the second subtitle" in clean_content
    assert "This is the third subtitle" in clean_content
    
    # Check that timestamp is included (only at the beginning since all are in the same minute)
    assert "[00:00:00]" in clean_content
    
    # Check that there are no duplicate lines
    lines = [line for line in clean_content.split('\n') if line and not (line.startswith('[') and line.endswith(']'))]
    assert len(lines) == len(set(lines))


@mock.patch("subprocess.run")
def test_youtube_loader_with_subtitles(mock_run):
    """Test loading subtitles from a YouTube video."""
    # Mock the subprocess.run to avoid actually calling yt-dlp
    mock_process = mock.Mock()
    mock_process.stdout = "Downloading subtitles..."
    mock_run.return_value = mock_process

    # Create a temporary directory with a mock subtitle file
    with tempfile.TemporaryDirectory() as temp_dir:
        # Mock the tempfile.TemporaryDirectory to return our controlled directory
        with mock.patch("tempfile.TemporaryDirectory") as mock_temp_dir:
            mock_temp_dir.return_value.__enter__.return_value = temp_dir

            # Create a mock subtitle file
            subtitle_path = Path(temp_dir) / "dQw4w9WgXcQ.en.vtt"
            subtitle_content = """WEBVTT

1
00:00:00.000 --> 00:00:03.000
This is a test subtitle

2
00:00:04.000 --> 00:00:07.000
For the YouTube fragment loader"""

            with open(subtitle_path, "w", encoding="utf-8") as f:
                f.write(subtitle_content)

            # Call the youtube_loader function
            fragment = youtube_loader("dQw4w9WgXcQ")

            # Check that the fragment was created correctly
            assert isinstance(fragment, llm.Fragment)
            assert fragment.source == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
            
            # Check that the fragment content contains the expected text
            fragment_content = str(fragment)
            assert "This is a test subtitle" in fragment_content
            assert "For the YouTube fragment loader" in fragment_content
            
            # Check that timestamp is included (only at the beginning since all are in the same minute)
            assert "[00:00:00]" in fragment_content


@mock.patch("subprocess.run")
def test_youtube_loader_with_auto_subtitles(mock_run):
    """Test loading auto-generated subtitles when regular subtitles are not available."""
    # Mock the subprocess.run to avoid actually calling yt-dlp
    def side_effect(*args, **kwargs):
        # Create a mock subtitle file only on the second call (auto-subtitles)
        if "--write-auto-sub" in args[0]:
            subtitle_path = Path(tempfile.gettempdir()) / "dQw4w9WgXcQ.en.vtt"
            with open(subtitle_path, "w", encoding="utf-8") as f:
                f.write("WEBVTT\n\n1\n00:00:00.000 --> 00:00:03.000\nAuto-generated subtitle")
        return mock.Mock()

    mock_run.side_effect = side_effect

    # Create a temporary directory for the test
    with tempfile.TemporaryDirectory() as temp_dir:
        # Mock the tempfile.TemporaryDirectory to return our controlled directory
        with mock.patch("tempfile.TemporaryDirectory") as mock_temp_dir:
            mock_temp_dir.return_value.__enter__.return_value = temp_dir

            # Call the youtube_loader function
            with mock.patch("os.listdir") as mock_listdir:
                # First call returns empty list (no regular subtitles)
                # Second call returns the auto-generated subtitle file
                mock_listdir.side_effect = [[], ["dQw4w9WgXcQ.en.vtt"]]
                
                # Create the auto-subtitle file
                subtitle_path = Path(temp_dir) / "dQw4w9WgXcQ.en.vtt"
                with open(subtitle_path, "w", encoding="utf-8") as f:
                    f.write("WEBVTT\n\n1\n00:00:00.000 --> 00:00:03.000\nAuto-generated subtitle")
                
                fragment = youtube_loader("dQw4w9WgXcQ")

                # Check that the fragment was created correctly
                assert isinstance(fragment, llm.Fragment)
                assert fragment.source == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
                
                # Check that the fragment content contains the expected text
                fragment_content = str(fragment)
                assert "Auto-generated subtitle" in fragment_content
                
                # Check that timestamps are included
                assert "[00:00:00]" in fragment_content


@mock.patch("subprocess.run")
def test_youtube_loader_no_subtitles(mock_run):
    """Test error handling when no subtitles are available."""
    # Mock the subprocess.run to avoid actually calling yt-dlp
    mock_run.return_value = mock.Mock()

    # Create a temporary directory for the test
    with tempfile.TemporaryDirectory() as temp_dir:
        # Mock the tempfile.TemporaryDirectory to return our controlled directory
        with mock.patch("tempfile.TemporaryDirectory") as mock_temp_dir:
            mock_temp_dir.return_value.__enter__.return_value = temp_dir

            # Mock os.listdir to return empty lists (no subtitle files found)
            with mock.patch("os.listdir", return_value=[]):
                # Call the youtube_loader function and expect a ValueError
                with pytest.raises(ValueError):
                    youtube_loader("dQw4w9WgXcQ")


@mock.patch("subprocess.run")
def test_youtube_loader_with_language(mock_run):
    """Test loading subtitles with a specific language."""
    # Mock the subprocess.run to avoid actually calling yt-dlp
    mock_process = mock.Mock()
    mock_process.stdout = "Downloading subtitles..."
    mock_run.return_value = mock_process

    # Create a temporary directory with a mock subtitle file
    with tempfile.TemporaryDirectory() as temp_dir:
        # Mock the tempfile.TemporaryDirectory to return our controlled directory
        with mock.patch("tempfile.TemporaryDirectory") as mock_temp_dir:
            mock_temp_dir.return_value.__enter__.return_value = temp_dir

            # Create a mock subtitle file
            subtitle_path = Path(temp_dir) / "dQw4w9WgXcQ.es.vtt"
            subtitle_content = """WEBVTT

1
00:00:00.000 --> 00:00:03.000
Este es un subtítulo de prueba

2
00:00:04.000 --> 00:00:07.000
Para el cargador de fragmentos de YouTube"""

            with open(subtitle_path, "w", encoding="utf-8") as f:
                f.write(subtitle_content)

            # Call the youtube_loader function with a language prefix
            fragment = youtube_loader("es:dQw4w9WgXcQ")

            # Check that the fragment was created correctly
            assert isinstance(fragment, llm.Fragment)
            assert fragment.source == "https://www.youtube.com/watch?v=dQw4w9WgXcQ&cc_lang_pref=es"
            
            # Check that the fragment content contains the expected text
            fragment_content = str(fragment)
            assert "Este es un subtítulo de prueba" in fragment_content
            assert "Para el cargador de fragmentos de YouTube" in fragment_content
            
            # Check that timestamp is included (only at the beginning since all are in the same minute)
            assert "[00:00:00]" in fragment_content
