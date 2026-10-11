#!/usr/bin/env python3
"""ELDRICK Club Fitter on Grok.

A terminal chat where Grok interviews a golfer, runs an ELDRICK fitting through
ELDRICK's remote MCP server, shows the specs and top picks, and finds a club
fitter. xAI connects to the MCP server for you (a server-side tool), so this
file never calls ELDRICK directly.

    pip install -r requirements.txt
    cp ../.env.example ../.env   # then fill in XAI_API_KEY and ELDRICK_API_KEY
    python grok_fitter.py

    python grok_fitter.py --print-config   # show the MCP tool config, no network

Docs: https://docs.x.ai/developers/tools/remote-mcp
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
TEMPLATE_DIR = HERE.parent
CONFIG_PATH = TEMPLATE_DIR / "eldrick-mcp.json"
PROMPT_PATH = TEMPLATE_DIR / "system-prompt.md"


def load_dotenv(path: Path) -> None:
    """Read KEY=value lines into os.environ. Values already set win."""
    if not path.is_file():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and value and key not in os.environ:
            os.environ[key] = value


def load_config() -> dict[str, Any]:
    return json.loads(CONFIG_PATH.read_text())


def eldrick_tool(config: dict[str, Any], eldrick_api_key: str | None, allowed_tools: list[str] | None = None) -> dict[str, Any]:
    """ELDRICK as an xAI Responses API `mcp` tool (documented field names).

    `authorization` is the ELDRICK key from the environment; xAI sends it to
    ELDRICK in the Authorization header. ELDRICK accepts it with or without
    the "Bearer " prefix.
    """
    tool = dict(config["tool"])
    tool["server_url"] = os.environ.get("ELDRICK_MCP_URL", tool["server_url"])
    tool["headers"] = dict(tool.get("headers", {}))
    if allowed_tools is not None:
        tool["allowed_tools"] = list(allowed_tools)
    if eldrick_api_key:
        tool["authorization"] = eldrick_api_key
    return tool


def sdk_mcp_kwargs(tool: dict[str, Any]) -> dict[str, Any]:
    """The same tool as keyword arguments for xai_sdk.tools.mcp().

    The native SDK names two fields differently: allowed_tools ->
    allowed_tool_names, headers -> extra_headers.
    """
    kwargs: dict[str, Any] = {
        "server_url": tool["server_url"],
        "server_label": tool["server_label"],
        "server_description": tool.get("server_description"),
        "allowed_tool_names": tool.get("allowed_tools"),
        "extra_headers": tool.get("headers") or None,
    }
    if tool.get("authorization"):
        kwargs["authorization"] = tool["authorization"]
    return kwargs


def redacted(value: dict[str, Any]) -> dict[str, Any]:
    out = dict(value)
    if out.get("authorization"):
        out["authorization"] = "<ELDRICK_API_KEY from env>"
    return out


def print_config(config: dict[str, Any]) -> None:
    tool = eldrick_tool(config, os.environ.get("ELDRICK_API_KEY"))
    print(json.dumps({
        "model": os.environ.get("GROK_MODEL", config["model"]),
        "responses_api_tool": redacted(tool),
        "xai_sdk_mcp_kwargs": redacted(sdk_mcp_kwargs(tool)),
    }, indent=2))


def require_env(name: str, where: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        sys.exit(f"Set {name} (get one at {where}). See ../.env.example.")
    return value


def chat_loop(config: dict[str, Any], model: str, show_tools: bool) -> None:
    xai_key = require_env("XAI_API_KEY", "https://console.x.ai")
    eldrick_key = require_env("ELDRICK_API_KEY", "https://api.eldrick.com")

    try:
        from xai_sdk import Client
        from xai_sdk.chat import system, user
        from xai_sdk.tools import mcp
    except ImportError:
        sys.exit("Install the xAI SDK first: pip install -r requirements.txt")

    client = Client(api_key=xai_key)
    chat = client.chat.create(
        model=model,
        messages=[system(PROMPT_PATH.read_text())],
        tools=[mcp(**sdk_mcp_kwargs(eldrick_tool(config, eldrick_key)))],
        include=["verbose_streaming"],
    )

    print("ELDRICK Club Fitter on Grok")
    print("Which club do you want fitted: driver, fairway wood, hybrid, irons or wedges? (exit to quit)\n")
    while True:
        try:
            text = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not text:
            continue
        if text.lower() in {"exit", "quit"}:
            return

        chat.append(user(text))
        print("\nELDRICK: ", end="", flush=True)
        response = None
        for response, chunk in chat.stream():
            if show_tools:
                for call in chunk.tool_calls:
                    print(f"\n  [calling {call.function.name}]", end="", flush=True)
            if chunk.content:
                print(chunk.content, end="", flush=True)
        print("\n")
        if response is not None:
            chat.append(response)


def main() -> None:
    load_dotenv(TEMPLATE_DIR / ".env")
    config = load_config()
    parser = argparse.ArgumentParser(description="ELDRICK Club Fitter on Grok")
    parser.add_argument("--print-config", action="store_true", help="print the MCP tool config (key redacted) and exit; no network")
    parser.add_argument("--model", default=os.environ.get("GROK_MODEL", config["model"]))
    parser.add_argument("--quiet-tools", action="store_true", help="don't print ELDRICK tool calls")
    args = parser.parse_args()

    if args.print_config:
        print_config(config)
        return
    chat_loop(config, args.model, show_tools=not args.quiet_tools)


if __name__ == "__main__":
    main()
