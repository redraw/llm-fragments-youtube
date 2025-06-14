# LLM YouTube Fragments Plugin

A plugin for [Simon Willison's LLM tool](https://github.com/simonw/llm) that adds a `youtube` fragment loader to download and use YouTube video subtitles in your prompts.

## Installation

1. Make sure you have the LLM tool installed:
   ```bash
   pip install llm
   ```

2. Install this plugin:
   ```bash
   llm install llm-fragments-youtube
   ```

   This will automatically install all dependencies, including yt-dlp.

## Usage

You can use the `youtube` or `yt` fragment in your LLM prompts to include subtitles from YouTube videos:

```bash
# Using a YouTube video ID
llm -f youtube:dQw4w9WgXcQ "summarize this video"

# You can also use the shorter 'yt' prefix
llm -f yt:dQw4w9WgXcQ "summarize this video"

# Continue chatting
llm -c "at which minute do they talk about ..."

# Language can also be specified
llm -f youtube:es:dQw4w9WgXcQ "resume el video"

# Using a full YouTube URL
llm -f youtube:https://www.youtube.com/watch?v=dQw4w9WgXcQ "summarize video"
```

## Development

### Running Tests

To run the tests, first install the package with test dependencies:

```bash
pip install -e ".[test]"
```

Then run the tests using pytest:

```bash
pytest
```

## License

Beerware
