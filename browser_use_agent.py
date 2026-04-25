#!/usr/bin/env python3
"""browser-use-agent — LLM-controlled browser automation."""

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path

G = "\033[92m"
R = "\033[91m"
Y = "\033[93m"
C = "\033[96m"
W = "\033[0m"
BOLD = "\033[1m"

SKILL_DIR = Path(__file__).parent
CONFIG_FILE = SKILL_DIR / "config.json"
RESULTS_DIR = SKILL_DIR / "results"
SCREENSHOTS_DIR = SKILL_DIR / "screenshots"
SCRIPTS_DIR = SKILL_DIR / "scripts"


def load_config():
    if CONFIG_FILE.exists():
        return json.loads(CONFIG_FILE.read_text())
    return {}


def save_config(cfg):
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2))


def get_llm(cfg):
    """Get the appropriate LLM based on config/env."""
    model = cfg.get("model", "gpt-4o")

    # Try OpenAI first
    api_key = os.environ.get("OPENAI_API_KEY") or cfg.get("openai_api_key")
    if api_key:
        try:
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(model=model, api_key=api_key)
        except ImportError:
            pass

    # Try Anthropic
    api_key = os.environ.get("ANTHROPIC_API_KEY") or cfg.get("anthropic_api_key")
    if api_key:
        try:
            from langchain_anthropic import ChatAnthropic
            return ChatAnthropic(model="claude-sonnet-4-20250514", api_key=api_key)
        except ImportError:
            pass

    print(f"{R}No LLM provider found.{W}")
    print(f"  Set OPENAI_API_KEY or ANTHROPIC_API_KEY env var.")
    print(f"  Or install langchain providers: {C}pip install langchain-openai langchain-anthropic{W}")
    sys.exit(1)


def check_browser_use():
    try:
        import browser_use
        return True
    except ImportError:
        print(f"{R}browser-use not installed.{W}")
        print(f"  Install: {C}pip install browser-use playwright && playwright install chromium{W}")
        return False


async def cmd_task(args):
    if not check_browser_use():
        sys.exit(1)

    cfg = load_config()
    headless = args.headless or cfg.get("headless", False)
    timeout = args.timeout or cfg.get("timeout", 120)

    from browser_use import Agent, BrowserConfig

    llm = get_llm(cfg)

    task = args.task
    print(f"{C}Task:{W} {task}")
    print(f"{C}Model:{W} {cfg.get('model', 'gpt-4o')}")
    print(f"{C}Headless:{W} {headless}")
    print(f"{C}Timeout:{W} {timeout}s\n")

    browser_config = BrowserConfig(headless=headless)
    agent = Agent(task=task, llm=llm, browser_config=browser_config)

    try:
        result = await asyncio.wait_for(agent.run(), timeout=timeout)
        output = {
            "task": task,
            "status": "completed",
            "result": str(result),
            "timestamp": datetime.now().isoformat(),
        }
        print(f"\n{G}Task completed:{W}")
        print(str(result)[:1000])

    except asyncio.TimeoutError:
        output = {
            "task": task,
            "status": "timeout",
            "error": f"Timed out after {timeout}s",
            "timestamp": datetime.now().isoformat(),
        }
        print(f"\n{R}Task timed out after {timeout}s{W}")
    except Exception as e:
        output = {
            "task": task,
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
        }
        print(f"\n{R}Task failed:{W} {e}")

    RESULTS_DIR.mkdir(exist_ok=True)
    out_file = RESULTS_DIR / f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    out_file.write_text(json.dumps(output, indent=2))
    print(f"{G}Results saved:{W} {out_file}")


async def cmd_screenshot(args):
    if not check_browser_use():
        sys.exit(1)

    cfg = load_config()
    headless = args.headless or cfg.get("headless", True)

    from playwright.async_api import async_playwright

    url = args.url
    print(f"{C}Capturing:{W} {url}")

    SCREENSHOTS_DIR.mkdir(exist_ok=True)
    filename = args.output or f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    out_path = SCREENSHOTS_DIR / filename

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        page = await browser.new_page(viewport={"width": 1280, "height": 720})
        await page.goto(url, wait_until="networkidle", timeout=30000)
        await page.screenshot(path=str(out_path), full_page=args.full_page)
        await browser.close()

    print(f"{G}Screenshot saved:{W} {out_path}")
    print(f"{Y}Size:{W} {out_path.stat().st_size / 1024:.1f} KB")


async def cmd_extract(args):
    if not check_browser_use():
        sys.exit(1)

    cfg = load_config()
    from playwright.async_api import async_playwright

    url = args.url
    print(f"{C}Extracting from:{W} {url}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(url, wait_until="networkidle", timeout=30000)

        data = {
            "url": url,
            "title": await page.title(),
            "content": await page.inner_text("body"),
            "links": await page.eval_on_selector_all("a[href]", "els => els.map(e => ({text: e.innerText, href: e.href}))"),
            "timestamp": datetime.now().isoformat(),
        }

        if args.selector:
            try:
                data["selected"] = await page.eval_on_selector_all(
                    args.selector,
                    "els => els.map(e => e.innerText)",
                )
            except Exception as e:
                data["selected_error"] = str(e)

        await browser.close()

    if args.output == "json":
        RESULTS_DIR.mkdir(exist_ok=True)
        out = RESULTS_DIR / f"extract_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        out.write_text(json.dumps(data, indent=2))
        print(f"{G}Data saved:{W} {out}")
    else:
        print(f"\n{Y}Title:{W} {data['title']}")
        content = data["content"][:500]
        print(f"\n{Y}Content:{W}\n{content}...")
        print(f"\n{Y}Links:{W} {len(data['links'])} found")


async def cmd_record(args):
    if not check_browser_use():
        sys.exit(1)

    cfg = load_config()

    task = args.task
    print(f"{C}Recording task:{W} {task}")
    print(f"{C}Steps:{W} {args.steps}\n")

    # Generate a Playwright script from a natural language task
    llm = get_llm(cfg)

    prompt = f"""Convert this browser automation task into a Python Playwright script.
Task: {task}
Number of steps: {args.steps}

Output ONLY valid Python code using async_playwright. No explanations.
The script should:
- Use async/await
- Launch chromium in non-headless mode
- Include page.goto, page.click, page.fill, page.screenshot as needed
- Add comments for each step
- Save a screenshot at the end to 'recorded_screenshot.png'
"""

    try:
        response = llm.invoke(prompt)
        code = response.content if hasattr(response, "content") else str(response)

        # Extract code block if wrapped
        if "```python" in code:
            code = code.split("```python")[1].split("```")[0]
        elif "```" in code:
            code = code.split("```")[1].split("```")[0]

        SCRIPTS_DIR.mkdir(exist_ok=True)
        script_name = args.output or f"recorded_{datetime.now().strftime('%Y%m%d_%H%M%S')}.py"
        script_path = SCRIPTS_DIR / script_name
        script_path.write_text(code.strip())

        print(f"{G}Script generated:{W} {script_path}")
        print(f"\n{Y}Preview:{W}")
        print(code.strip()[:800])

    except Exception as e:
        print(f"{R}Failed to generate script:{W} {e}")
        sys.exit(1)


async def cmd_config(args):
    cfg = load_config()

    if args.model:
        cfg["model"] = args.model
        print(f"{G}Model set to {args.model}.{W}")

    if args.headless is not None:
        cfg["headless"] = args.headless
        print(f"{G}Headless mode: {args.headless}.{W}")

    if args.timeout:
        cfg["timeout"] = int(args.timeout)
        print(f"{G}Timeout set to {args.timeout}s.{W}")

    if args.set_openai_key:
        cfg["openai_api_key"] = args.set_openai_key
        print(f"{G}OpenAI API key saved.{W}")

    if args.set_anthropic_key:
        cfg["anthropic_api_key"] = args.set_anthropic_key
        print(f"{G}Anthropic API key saved.{W}")

    if any([args.model, args.headless is not None, args.timeout, args.set_openai_key, args.set_anthropic_key]):
        save_config(cfg)

    if not any([args.model, args.headless is not None, args.timeout, args.set_openai_key, args.set_anthropic_key]):
        print(f"{BOLD}Current configuration:{W}")
        if cfg:
            for k, v in cfg.items():
                if "key" in k.lower():
                    masked = str(v)[:6] + "..." + str(v)[-4:] if len(str(v)) > 10 else "***"
                    print(f"  {Y}{k}:{W} {masked}")
                else:
                    print(f"  {Y}{k}:{W} {v}")
        else:
            print(f"  {Y}(empty — using defaults){W}")
        print(f"\n  {Y}env OPENAI_API_KEY:{W} {'set' if os.environ.get('OPENAI_API_KEY') else 'not set'}")
        print(f"  {Y}env ANTHROPIC_API_KEY:{W} {'set' if os.environ.get('ANTHROPIC_API_KEY') else 'not set'}")


async def main():
    parser = argparse.ArgumentParser(
        description="LLM-controlled browser automation with browser-use",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command")

    # task
    p = sub.add_parser("task", help="Execute a browser task with natural language")
    p.add_argument("task", help="Task description in natural language")
    p.add_argument("--headless", action="store_true", help="Run headless")
    p.add_argument("--timeout", type=int, help="Timeout in seconds")

    # screenshot
    p = sub.add_parser("screenshot", help="Capture a page screenshot")
    p.add_argument("url", help="URL to capture")
    p.add_argument("--output", help="Output filename")
    p.add_argument("--full-page", action="store_true", help="Full page capture")
    p.add_argument("--headless", action="store_true", default=True, help="Run headless")

    # extract
    p = sub.add_parser("extract", help="Extract data from a web page")
    p.add_argument("url", help="URL to extract from")
    p.add_argument("--selector", help="CSS selector for specific elements")
    p.add_argument("--output", choices=["json", "text"], default="text", help="Output format")

    # record
    p = sub.add_parser("record", help="Generate a Playwright script from a task")
    p.add_argument("task", help="Task description")
    p.add_argument("--steps", type=int, default=5, help="Approximate number of steps")
    p.add_argument("--output", help="Output script filename")

    # config
    p = sub.add_parser("config", help="Configure defaults")
    p.add_argument("--model", help="LLM model to use")
    p.add_argument("--headless", action="store_true", help="Set headless mode")
    p.add_argument("--timeout", help="Set timeout in seconds")
    p.add_argument("--set-openai-key", help="Set OpenAI API key")
    p.add_argument("--set-anthropic-key", help="Set Anthropic API key")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return

    cmds = {
        "task": cmd_task,
        "screenshot": cmd_screenshot,
        "extract": cmd_extract,
        "record": cmd_record,
        "config": cmd_config,
    }
    await cmds[args.command](args)


if __name__ == "__main__":
    asyncio.run(main())
