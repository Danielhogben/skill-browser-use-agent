# browser-use-agent — LLM-Controlled Browser Automation

Natural-language browser automation using [browser-use](https://github.com/browser-use/browser-use). An LLM controls the browser to perform tasks described in plain English.

## Capabilities

- **task** — Execute a browser automation task described in natural language
- **record** — Record browser actions as a reusable Python script
- **screenshot** — Capture screenshots of web pages
- **extract** — Extract structured data from web pages
- **config** — Configure model provider, headless mode, timeouts

## Setup

```bash
pip install browser-use playwright
playwright install chromium
```

Set an LLM provider API key (OpenAI, Anthropic, etc.):

```bash
export OPENAI_API_KEY="sk-..."
# or
export ANTHROPIC_API_KEY="sk-ant-..."
```

## Usage

```bash
# Run a natural language browser task
python3 browser_use_agent.py task "Go to Google and search for 'Python tutorials', then click the first result"

# Capture a screenshot
python3 browser_use_agent.py screenshot https://example.com

# Extract data from a page
python3 browser_use_agent.py extract https://news.ycombinator.com --output json

# Configure defaults
python3 browser_use_agent.py config --model gpt-4o --headless --timeout 120
```

## Configuration

Stored in `config.json` within the skill directory. Supports:
- **model** — LLM model to use (default: gpt-4o)
- **headless** — Run browser without visible window
- **timeout** — Task timeout in seconds
- **api_key** — API key (or use env vars)

## Output

- Task results saved to `results/` as JSON
- Screenshots saved to `screenshots/`
- Recorded scripts saved to `scripts/`
