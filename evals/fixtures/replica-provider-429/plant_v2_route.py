"""Plant the provider-429 task in a built chatsvc: the new `/v2/chat` route on the fast models.

The route is what a team would add in one commit: its settings, its limits, its docs, its
handler, and a traffic sample taken from the gateway. Its handler calls the transport directly,
and in doing so (1) builds the provider path from what the caller asked for, so an alias such as
`fast` reaches the provider as a model id that does not exist (404), and (2) tries again at once
on any answer but 200, so a refused call on the shared key is followed by more refused calls
(429), and a 404 is tried again too. Run from the workspace.

Standard library only.
"""

from __future__ import annotations

import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent


def edit(name: str, old: str, new: str) -> None:
    path = Path(name)
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"plant_v2_route.py: {name} does not hold {old!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


ROUTE = """
[route:fast]
path = /v2/chat
key = pool-b
default_model = chat-fast-2
aliases = fast=chat-fast-2, fast-long=chat-fast-2-long
max_attempts = 4
timeout = 10

[embed]"""

HANDLER = '''

def fast_chat(service, route, request):
    """Chat on the fast models. The fast models stream their first token in well under a second,
    so this route calls the transport itself rather than going through the client's retry
    bookkeeping, and tries again straight away when an attempt does not succeed."""
    messages = messages_of(request)
    max_tokens = max_tokens_of(request)
    model = request.get("model") or route.default_model
    body = json.dumps({"messages": messages, "max_tokens": max_tokens}).encode("utf-8")
    headers = {"authorization": f"Bearer {route.key}", "content-type": "application/json"}
    path = f"/v1/models/{model}:generate"
    for attempt in range(1, route.max_attempts + 1):
        response = service.transport.send("POST", path, headers, body)
        service.log(f"upstream path={path} attempt={attempt} status={response.status}")
        if response.status == 200:
            answer = response.json()
            return reply(
                200,
                {
                    "model": model,
                    "output": answer.get("output", ""),
                    "usage": answer.get("usage", {}),
                },
            )
    return reply(response.status, {"error": "upstream_error", "status": response.status})


HANDLERS = {"fast": fast_chat}


def handler_for(route):
    """The handler of a chat route: its own where it has one, else `chat`."""
    return HANDLERS.get(route.name, chat)
'''


def main() -> None:
    edit("config/chatsvc.ini", "\n[embed]", ROUTE)
    edit(
        "config/limits.conf",
        "limit_req_zone $api_key zone=embed:1m rate=20r/m;",
        "limit_req_zone $api_key zone=chat_v2:1m rate=5r/s;\n"
        "limit_req_zone $api_key zone=embed:1m rate=20r/m;",
    )
    edit(
        "config/limits.conf",
        "location /v1/embed {",
        "location /v2/chat {\n"
        "    limit_req zone=chat_v2 burst=10 nodelay;\n"
        "    client_max_body_size 64k;\n"
        "}\n\n"
        "location /v1/embed {",
    )
    edit(
        "docs/configuration.md",
        "aliases `large`, `small`.\n",
        "aliases `large`, `small`.\n"
        "- `/v2/chat` (`route:fast`): pool-b, `chat-fast-2` by default; aliases `fast`,"
        " `fast-long`.\n",
    )
    edit(
        "docs/limits.md",
        "| `/v1/embed` |",
        "| `/v2/chat` | chat_v2 | 5/s | 10 | 64k |\n| `/v1/embed` |",
    )
    edit("docs/provider.md", "- `pool-b`: reserved for the fast models.", "- `pool-b`: `/v2/chat`.")
    edit(
        "CHANGELOG.md",
        "## 1.8.0 (unreleased)\n\n",
        "## 1.8.0 (unreleased)\n\n- Added: `/v2/chat`, on the fast models (pool-b).\n",
    )
    edit("chatsvc/routes.py", '"""The request handlers', '"""The request handlers')
    path = Path("chatsvc/routes.py")
    path.write_text(path.read_text(encoding="utf-8") + HANDLER, encoding="utf-8")
    edit(
        "chatsvc/app.py",
        "            return routes.chat(self, route, request)",
        "            return routes.handler_for(route)(self, route, request)",
    )
    Path("traffic").mkdir(exist_ok=True)
    shutil.copyfile(HERE / "traffic-v2-2026-10-20.jsonl", Path("traffic") / "v2-2026-10-20.jsonl")


if __name__ == "__main__":
    main()
