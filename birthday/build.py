#!/usr/bin/env python3
"""Build the plan-chooser page from plans.md.

plans.md is the single source of truth: it is the text that gets pasted into
LINE verbatim, and it is also parsed here into the route cards. Anything that
would clutter that text — travel times, fares, day-of-week conditions — lives
in META below instead, keyed by route number. Every META value is taken from
what the route text already says; nothing new is invented here.

Two files come out of one template, because the two destinations disagree on
what a document is:

  index.html     complete standalone document (charset + viewport + title),
                 for opening straight from the repo
  artifact.html  the same body fragment on its own, for publishing, where the
                 host supplies <!doctype>/<head>/<body> around it
"""

import re
from pathlib import Path

HERE = Path(__file__).parent
SOURCE = HERE / "plans.md"
TEMPLATE = HERE / "page.template.html"
OUT_PAGE = HERE / "index.html"
OUT_FRAGMENT = HERE / "artifact.html"

PAGE_TITLE = "おひとり様誕生日 ご褒美プラン｜全6ルート"

MARKERS = {
    "intro": "<!--INTRO-->",
    "board": "<!--BOARD-->",
    "routes": "<!--ROUTES-->",
    "note": "<!--NOTE-->",
    "raw": "<!--RAW_TEXT-->",
}

# The band behind each board row runs 7:00 to 18:00 — early enough for the
# 07:50 departure, ending at the dinner everyone converges on.
BAND_START, BAND_END = 7 * 60, 18 * 60

META = {
    1: {"dest": "池袋", "move": "徒歩のみ", "fare": "追加料金なし", "day": "いつでも"},
    2: {"dest": "目白・雑司が谷", "move": "JR1駅・都電", "fare": "追加料金なし", "day": "いつでも"},
    3: {"dest": "鎌倉", "move": "湘南新宿ライン 約1時間", "fare": "グリーン券", "day": "いつでも"},
    4: {"dest": "館山", "move": "特急さざなみ 2時間6分", "fare": "指定席 +1,360円", "day": "土日祝のみ"},
    5: {"dest": "千葉・幕張", "move": "成田エクスプレス 45分", "fare": "指定席 +1,290円", "day": "平日向き"},
    6: {"dest": "大洗・水戸", "move": "特急ひたち 1時間30分", "fare": "指定席 +1,580円", "day": "いつでも"},
}

HEADING = re.compile(r"^##\s+([🟦🟫🟩🟨🟥🟪])\s*(\d+)\.\s*(.+?)\s*$")
STOP = re.compile(r"^\*\s*(\d{1,2}):(\d{2})：(.+?)\s*$")
BADGE = re.compile(r"^【(.+?)】\s*")
THEME = re.compile(r"\s*🐚\s*(\S+)$")
LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
BOLD = re.compile(r"\*\*([^*]+)\*\*")
# Only the shared ending splits off as its own stop; the arrows inside a
# departure line ("07:50 …乗車 ➔ 09:56 館山駅到着") stay where they are.
TERMINUS = re.compile(r"\s*➔\s*(\d{1,2}:\d{2})\s*(池袋で合流)\s*$")


def esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def inline(text: str) -> str:
    """Markdown links and bold, on already-escaped text."""
    out = esc(text)
    out = LINK.sub(
        lambda m: f'<a href="{m.group(2)}" target="_blank" rel="noopener">{m.group(1)}</a>',
        out,
    )
    return BOLD.sub(r"<strong>\1</strong>", out)


def parse(markdown: str) -> tuple[str, str, list[dict]]:
    intro, note, routes = "", "", []
    current = None

    for line in markdown.splitlines():
        heading = HEADING.match(line)
        if heading:
            _, number, title = heading.groups()
            badge = BADGE.match(title)
            if badge:
                title = title[badge.end() :]
            theme = THEME.search(title)
            if theme:
                title = title[: theme.start()]
            current = {
                "n": int(number),
                "title": title.strip(),
                "badge": badge.group(1) if badge else "",
                "theme": theme.group(1) if theme else "",
                "lede": "",
                "stops": [],
                "end": None,
            }
            routes.append(current)
            continue

        if line.startswith("## 🎂"):
            current = None
            continue

        stop = STOP.match(line)
        if stop and current:
            hour, minute, text = stop.groups()
            end = TERMINUS.search(text)
            if end:
                text = text[: end.start()]
                current["end"] = {"time": end.group(1), "text": end.group(2)}
            current["stops"].append(
                {
                    # Zero-padded so the times line up as a column, tabular
                    # figures doing the rest.
                    "time": f"{int(hour):02d}:{minute}",
                    "minutes": int(hour) * 60 + int(minute),
                    "text": inline(text),
                }
            )
            continue

        body = line.strip()
        if not body or body.startswith("---"):
            continue
        if body.startswith("💡"):
            # The panel is already labelled 共通の持ち物, so drop the label the
            # LINE text needs to carry inline.
            note = inline(re.sub(r"^全プラン共通持ち物：\s*", "", body.lstrip("💡 ")))
        elif current and not current["lede"]:
            current["lede"] = inline(body)
        elif not routes and not intro:
            intro = inline(body)

    return intro, note, routes


def band(route: dict) -> str:
    """A 7:00–18:00 strip: the day's span filled in, one notch per stop.

    Reading the six of them stacked is how you see that route 4 asks for a
    07:50 start and route 1 does not get going until 11:30.
    """
    span = BAND_END - BAND_START
    start = route["stops"][0]["minutes"]
    left = (start - BAND_START) / span * 100
    notches = "".join(
        f'<i style="left:{(s["minutes"] - BAND_START) / span * 100:.2f}%"></i>'
        for s in route["stops"]
    )
    return (
        f'<span class="band" aria-hidden="true">'
        f'<span class="band-fill" style="left:{left:.2f}%"></span>{notches}</span>'
    )


def board_row(route: dict) -> str:
    meta = META[route["n"]]
    day_class = " is-limited" if meta["day"] == "土日祝のみ" else ""
    return f"""      <a class="row" href="#route-{route["n"]}" style="--line:var(--l{route["n"]})">
        <span class="sym">{route["n"]}</span>
        <span class="row-main">
          <span class="row-head">
            <span class="dest">{esc(meta["dest"])}</span>
            <span class="day{day_class}">{esc(meta["day"])}</span>
          </span>
          <span class="row-meta"><span class="seg">{esc(meta["move"])}</span><span class="seg">{esc(meta["fare"])}</span><span class="seg"><span class="num">{route["stops"][0]["time"]}</span> スタート</span></span>
          {band(route)}
        </span>
      </a>"""


def route_section(route: dict) -> str:
    meta = META[route["n"]]
    badge = f'<span class="badge">{esc(route["badge"])}</span>' if route["badge"] else ""
    theme = f'<span class="theme">{esc(route["theme"])}</span>' if route["theme"] else ""
    stops = "\n".join(
        f"""          <li class="stop">
            <span class="t num">{s["time"]}</span>
            <span class="what">{s["text"]}</span>
          </li>"""
        for s in route["stops"]
    )
    end = ""
    if route["end"]:
        end = f"""
          <li class="stop stop-end">
            <span class="t num">{route["end"]["time"]}</span>
            <span class="what">{esc(route["end"]["text"])}</span>
          </li>"""
    return f"""      <section class="route" id="route-{route["n"]}" style="--line:var(--l{route["n"]})">
        <header class="route-head">
          <span class="sym">{route["n"]}</span>
          <div class="route-titles">
            <span class="eyebrow">{badge}{theme}</span>
            <h2>{esc(route["title"])}</h2>
          </div>
        </header>
        <p class="lede">{route["lede"]}</p>
        <dl class="facts">
          <div><dt>移動</dt><dd>{esc(meta["move"])}</dd></div>
          <div><dt>きっぷ</dt><dd>{esc(meta["fare"])}</dd></div>
          <div><dt>曜日</dt><dd>{esc(meta["day"])}</dd></div>
        </dl>
        <ol class="timeline">
{stops}{end}
        </ol>
      </section>"""


def main() -> None:
    markdown = SOURCE.read_text(encoding="utf-8")
    intro, note, routes = parse(markdown)

    if len(routes) != 6:
        raise SystemExit(f"expected 6 routes in {SOURCE.name}, parsed {len(routes)}")
    missing = [r["n"] for r in routes if not r["stops"] or not r["lede"]]
    if missing:
        raise SystemExit(f"routes missing stops or description: {missing}")
    unknown = [r["n"] for r in routes if r["n"] not in META]
    if unknown:
        raise SystemExit(f"no META entry for routes: {unknown}")

    template = TEMPLATE.read_text(encoding="utf-8")
    for marker in MARKERS.values():
        if marker not in template:
            raise SystemExit(f"marker {marker} missing from {TEMPLATE.name}")

    fragment = template
    fragment = fragment.replace(MARKERS["intro"], intro)
    fragment = fragment.replace(MARKERS["note"], note)
    fragment = fragment.replace(
        MARKERS["board"], "\n".join(board_row(r) for r in routes).strip()
    )
    fragment = fragment.replace(
        MARKERS["routes"], "\n".join(route_section(r) for r in routes).strip()
    )
    # The copy button reads this block's textContent, so it has to stay the
    # markdown byte-for-byte — escaped, not rendered.
    fragment = fragment.replace(MARKERS["raw"], esc(markdown.strip()))

    OUT_FRAGMENT.write_text(fragment, encoding="utf-8")
    OUT_PAGE.write_text(
        "<!doctype html>\n"
        '<html lang="ja">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{PAGE_TITLE}</title>\n</head>\n<body>\n{fragment}\n</body>\n</html>\n",
        encoding="utf-8",
    )

    for out in (OUT_PAGE, OUT_FRAGMENT):
        print(f"wrote {out.relative_to(HERE.parent)} ({out.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
