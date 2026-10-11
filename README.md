# ELDRICK Club Fitter on Grok

A starter for building a golf club fitter on Grok with the xAI API. Grok
interviews the golfer, runs an ELDRICK fitting, shows the specs and top picks
with store links, and finds a club fitter nearby.

Built on 100,000+ fittings: trained on 80,000, plus 25,000+ ELDRICK has done itself.

ELDRICK is a remote MCP server at `https://api.eldrick.com/mcp`. xAI's API
attaches remote MCP servers as a server-side tool: you name the server in the
request, and xAI connects to it and calls its tools for you. Your code never
calls ELDRICK directly. See xAI's
[Remote MCP Tools](https://docs.x.ai/developers/tools/remote-mcp) guide.

| File | What it is |
| --- | --- |
| `eldrick-mcp.json` | The ELDRICK `mcp` tool (URL, label, allowed tools, attribution headers). Shared by both starters. No key in it. |
| `system-prompt.md` | The interview: club, handedness, speed, miss, then optional extras. Then fit, show, offer next steps. |
| `python/grok_fitter.py` | CLI chat on the xAI Python SDK (`xai-sdk`). |
| `typescript/grok-fitter.ts` | The same chat on xAI's OpenAI-compatible Responses API, with plain `fetch`. |
| `.env.example` | Every setting. Copy to `.env`. |

## Setup

1. Get an xAI API key at [console.x.ai](https://console.x.ai).
2. Get an ELDRICK developer key (`eld_...`) at [api.eldrick.com](https://api.eldrick.com). Every account includes 10 fittings a month; searching, scoring, comparing, grip sizing, bag gapping and finding fitters don't use one.
3. Put both in `.env`:

```bash
cp .env.example .env
# edit .env: XAI_API_KEY=...  ELDRICK_API_KEY=eld_...
```

Keys stay in the environment. They never go in source, in the system prompt or
in a tool argument.

## Run it

Python (3.10+):

```bash
cd python
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
python grok_fitter.py
```

TypeScript (Node 20):

```bash
export XAI_API_KEY=... ELDRICK_API_KEY=eld_...
npx tsx typescript/grok-fitter.ts
```

Both take `--print-config` to show the exact tool they send (key redacted),
with no network calls.

```
You: driver please
ELDRICK: Right- or left-handed?
You: right, about 98 mph, I slice it
  [calling analyze_fitting]
ELDRICK: (loft, shaft, length, lie and swing weight, then the top picks with store links) Fit by ELDRICK
```

## How ELDRICK is attached

Python, xAI SDK (`xai_sdk.tools.mcp`; the SDK spells two fields
`allowed_tool_names` and `extra_headers`):

```python
import os
from xai_sdk import Client
from xai_sdk.chat import system, user
from xai_sdk.tools import mcp

client = Client(api_key=os.environ["XAI_API_KEY"])
chat = client.chat.create(
    model="grok-4.7",
    messages=[system(open("system-prompt.md").read())],
    tools=[mcp(
        server_url="https://api.eldrick.com/mcp",
        server_label="eldrick",
        authorization=os.environ["ELDRICK_API_KEY"],
        allowed_tool_names=["analyze_fitting", "get_fitting", "score_clubs", "build_store_link", "find_fitter"],
        extra_headers={"X-ELDRICK-Platform": "grok"},
    )],
)
chat.append(user("Fit me for a driver. Right-handed, 98 mph, I slice it."))
print(chat.sample().content)
```

Responses API (OpenAI-compatible: `base_url="https://api.x.ai/v1"` with the
OpenAI SDK, or raw HTTP):

```bash
curl https://api.x.ai/v1/responses \
  -H "Authorization: Bearer $XAI_API_KEY" -H "Content-Type: application/json" \
  -d '{
    "model": "grok-4.7",
    "input": [{"role": "user", "content": "Fit me for a driver. Right-handed, 98 mph, I slice it."}],
    "tools": [{
      "type": "mcp",
      "server_url": "https://api.eldrick.com/mcp",
      "server_label": "eldrick",
      "authorization": "'"$ELDRICK_API_KEY"'",
      "headers": {"X-ELDRICK-Platform": "grok"}
    }]
  }'
```

Notes:

- `authorization` is the ELDRICK key. xAI puts it in the Authorization header
  of its calls to ELDRICK; ELDRICK accepts it with or without `Bearer `.
- `allowed_tools` keeps Grok to the tools you list. Leave it out and Grok sees
  every ELDRICK tool.
- `X-ELDRICK-Platform: grok` puts your traffic under Grok in ELDRICK's usage
  reports. Add `X-ELDRICK-Traffic: test` while you build, so test runs stay out
  of them. Neither header changes billing or limits.
- xAI documents remote MCP for the Responses API and the native SDK, not for
  the legacy Chat Completions endpoint.
- The model is `grok-4.7` (xAI's current flagship as of 2026-10-09); set
  `GROK_MODEL` to change it.

## Fittings and cost

`analyze_fitting` uses one of the account's fittings; every other tool in the
starter is free. The system prompt tells Grok to send an `idempotencyKey`, wait
on `get_fitting` when a fitting is still running, and retry a failed one with
the returned key, so a retry is never charged twice. A fitting takes about 20
to 50 seconds.

## Testing

`npm test` runs `server/lib/grok-bot-template.test.ts`, which checks this
template offline: the tool matches xAI's documented `mcp` fields, names only
tools ELDRICK serves, carries no key, and the Python starter prints the same
config. It never calls xAI or ELDRICK. To also run one live call (a free
`search_clubs` only, never a fitting):

```bash
XAI_API_KEY=... ELDRICK_API_KEY=eld_... ELDRICK_GROK_LIVE_TEST=1 \
  npx tsx --test server/lib/grok-bot-template.test.ts
```

## Show the attribution

When you show a fitting, show "Fit by ELDRICK". Setup for every other assistant
is at [api.eldrick.com/connect](https://api.eldrick.com/connect).
