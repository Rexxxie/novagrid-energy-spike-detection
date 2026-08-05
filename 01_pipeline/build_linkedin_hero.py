"""
NovaGrid — LinkedIn hero image
==============================
Composes a single 4:5 portrait image of the dashboard, framed in a browser
window on a branded plane:

    06_linkedin/dashboard_hero_dark.png     1080 x 1350 (rendered at 2160 x 2700)
    06_linkedin/dashboard_hero_light.png    the same shot in the light theme

The dashboard is embedded live in an iframe and scaled with a CSS transform
rather than screenshotted and shrunk, so every label stays vector-sharp.

Run after build_dashboard.py:  python3 01_pipeline/build_linkedin_hero.py
Requires Google Chrome.
"""

from __future__ import annotations

import http.server
import socketserver
import subprocess
import threading
from contextlib import closing
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DASH = ROOT / "03_dashboard"
OUT = ROOT / "06_linkedin"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

BYLINE = "Rexley Adio"          # change this line to re-brand the image
HANDLE = "Data Analyst"

# canvas 1080x1350 (LinkedIn's tallest un-cropped feed ratio)
W, H = 1080, 1350
FRAME_W = 968                   # browser window width on the canvas
VIEW_W = 1420                   # CSS width the dashboard is rendered at
SCALE = FRAME_W / VIEW_W
VIEW_H = 1352                   # how much of the page to show, in CSS px
WINDOW_TOP = 384                # clears the headline block
FRAME_H = 840                   # viewport height; stops clear of the footer

THEMES = {
    "dark": dict(
        plane="#0b0b0b", ink="#ffffff", ink2="#c3c2b7", muted="#7c7a74",
        accent="#3987e5", crit="#e05555", bar="#1c1c1b", edge="#2a2a28",
        glow="rgba(57,135,229,.20)", shadow="rgba(0,0,0,.65)",
    ),
    "light": dict(
        plane="#f4f4f1", ink="#0b0b0b", ink2="#52514e", muted="#898781",
        accent="#2a78d6", crit="#d03b3b", bar="#e8e8e3", edge="#d8d7d0",
        glow="rgba(42,120,214,.16)", shadow="rgba(11,11,11,.20)",
    ),
}

PAGE = """<!doctype html><html><head><meta charset="utf-8"><style>
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
html, body {{ width: {W}px; height: {H}px; overflow: hidden;
  background: {plane}; -webkit-print-color-adjust: exact; }}
.canvas {{
  width: {W}px; height: {H}px; position: relative; overflow: hidden;
  background: {plane}; color: {ink};
  font-family: system-ui, -apple-system, "Helvetica Neue", Arial, sans-serif;
  padding: 62px 56px 0;
}}
.glow {{ position: absolute; right: -260px; top: -300px; width: 900px; height: 900px;
  border-radius: 50%; background: radial-gradient(circle, {glow} 0%, transparent 66%); }}
.eyebrow {{ font-size: 17px; letter-spacing: .17em; text-transform: uppercase;
  color: {muted}; font-weight: 500; margin-bottom: 18px; position: relative; }}
h1 {{ font-size: 50px; line-height: 1.1; letter-spacing: -.028em; font-weight: 600;
  position: relative; }}
h1 .hl {{ color: {crit}; }}
.sub {{ font-size: 19.5px; line-height: 1.5; color: {ink2}; margin-top: 16px;
  max-width: 52ch; position: relative; }}

/* browser window */
.window {{
  position: absolute; left: 56px; top: {WINDOW_TOP}px; width: {FRAME_W}px;
  border-radius: 16px; overflow: hidden; border: 1px solid {edge};
  box-shadow: 0 40px 90px -20px {shadow}, 0 0 0 1px {edge};
  background: {bar};
}}
.bar {{ height: 40px; background: {bar}; display: flex; align-items: center;
  padding: 0 16px; gap: 8px; border-bottom: 1px solid {edge}; }}
.dot {{ width: 11px; height: 11px; border-radius: 50%; }}
.url {{ margin-left: 14px; font-size: 12.5px; color: {muted};
  background: {plane}; border: 1px solid {edge}; border-radius: 7px;
  padding: 4px 14px; }}
.viewport {{ width: {FRAME_W}px; height: {frame_h}px; overflow: hidden; position: relative; }}
iframe {{ width: {VIEW_W}px; height: {VIEW_H}px; border: 0;
  transform: scale({SCALE}); transform-origin: 0 0; }}
.fade {{ position: absolute; left: 0; right: 0; bottom: 0; height: 130px;
  background: linear-gradient(to bottom, transparent, {plane} 82%); }}

.foot {{ position: absolute; left: 56px; right: 56px; bottom: 40px;
  display: flex; justify-content: space-between; align-items: center;
  font-size: 17px; color: {muted}; }}
.foot b {{ color: {ink2}; font-weight: 600; }}
.tag {{ border: 1px solid {edge}; border-radius: 99px; padding: 6px 16px;
  font-size: 15px; color: {ink2}; }}
</style></head><body>
<div class="canvas">
  <div class="glow"></div>
  <div class="eyebrow">Interactive dashboard · Python + HTML</div>
  <h1>6,720 smart-meter readings,<br>and a rule that was<br><span class="hl">watching the wrong homes.</span></h1>
  <div class="sub">One self-contained HTML file — every chart filters together, and none of it
  needs a server or a Tableau licence.</div>

  <div class="window">
    <div class="bar">
      <span class="dot" style="background:#ec6a5e"></span>
      <span class="dot" style="background:#f4bf4f"></span>
      <span class="dot" style="background:#61c554"></span>
      <span class="url">novagrid_dashboard.html</span>
    </div>
    <div class="viewport">
      <iframe id="f" src="novagrid_dashboard.html" scrolling="no"></iframe>
      <div class="fade"></div>
    </div>
  </div>

  <div class="foot">
    <span><b>{BYLINE}</b> · {HANDLE}</span>
    <span class="tag">NovaGrid Energy · case study</span>
  </div>
</div>
<script>
  const f = document.getElementById("f");
  f.addEventListener("load", () => {{
    f.contentDocument.documentElement.setAttribute("data-theme", "{theme}");
  }});
</script>
</body></html>"""


def free_port() -> int:
    import socket
    with closing(socket.socket()) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def main() -> None:
    OUT.mkdir(exist_ok=True)
    written = []

    for theme, c in THEMES.items():
        html = PAGE.format(W=W, H=H, FRAME_W=FRAME_W, VIEW_W=VIEW_W, VIEW_H=VIEW_H,
                           SCALE=round(SCALE, 5), frame_h=FRAME_H,
                           WINDOW_TOP=WINDOW_TOP, theme=theme,
                           BYLINE=BYLINE, HANDLE=HANDLE, **c)
        # written beside the dashboard so the iframe is same-origin and the
        # parent can stamp the theme onto it
        p = DASH / f".hero_{theme}.html"
        p.write_text(html)
        written.append(p)

    port = free_port()
    handler = lambda *a, **k: http.server.SimpleHTTPRequestHandler(  # noqa: E731
        *a, directory=str(DASH), **k)
    with socketserver.TCPServer(("127.0.0.1", port), handler) as srv:
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        for theme in THEMES:
            out = OUT / f"dashboard_hero_{theme}.png"
            subprocess.run(
                [CHROME, "--headless=new", "--disable-gpu", "--no-sandbox",
                 "--hide-scrollbars", "--force-device-scale-factor=2",
                 f"--window-size={W},{H}", "--virtual-time-budget=8000",
                 f"--screenshot={out}",
                 f"http://127.0.0.1:{port}/.hero_{theme}.html"],
                check=True, capture_output=True, timeout=180)
            print(f"{out.name}  ({out.stat().st_size / 1024:.0f} KB, "
                  f"{W * 2} × {H * 2} px)")
        srv.shutdown()

    for p in written:
        p.unlink()


if __name__ == "__main__":
    main()
