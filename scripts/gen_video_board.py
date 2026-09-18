"""Generate docs/video-board.excalidraw for the tie-break video."""

from __future__ import annotations

import json
import random
import time
from pathlib import Path

random.seed(42)
NOW = int(time.time() * 1000)
elements: list[dict] = []
_eid = 0


def nid() -> str:
    global _eid
    _eid += 1
    return f"e{_eid}"


def seed() -> int:
    return random.randint(1, 2**31)


def rect(
    x: float,
    y: float,
    w: float,
    h: float,
    bg: str = "#f8fafc",
    stroke: str = "#1e293b",
    sw: float = 2,
    rounded: bool = True,
) -> dict:
    el = {
        "id": nid(),
        "type": "rectangle",
        "x": x,
        "y": y,
        "width": w,
        "height": h,
        "angle": 0,
        "strokeColor": stroke,
        "backgroundColor": bg,
        "fillStyle": "solid",
        "strokeWidth": sw,
        "strokeStyle": "solid",
        "roughness": 0,
        "opacity": 100,
        "groupIds": [],
        "frameId": None,
        "roundness": {"type": 3} if rounded else None,
        "seed": seed(),
        "version": 1,
        "versionNonce": seed(),
        "isDeleted": False,
        "boundElements": [],
        "updated": NOW,
        "link": None,
        "locked": False,
    }
    elements.append(el)
    return el


def text(
    x: float,
    y: float,
    t: str,
    size: float = 20,
    color: str = "#0f172a",
    w: float | None = None,
) -> dict:
    width = w if w is not None else max(40.0, len(t) * size * 0.55)
    height = size * 1.35
    el = {
        "id": nid(),
        "type": "text",
        "x": x,
        "y": y,
        "width": width,
        "height": height,
        "angle": 0,
        "strokeColor": color,
        "backgroundColor": "transparent",
        "fillStyle": "solid",
        "strokeWidth": 1,
        "strokeStyle": "solid",
        "roughness": 0,
        "opacity": 100,
        "groupIds": [],
        "frameId": None,
        "roundness": None,
        "seed": seed(),
        "version": 1,
        "versionNonce": seed(),
        "isDeleted": False,
        "boundElements": None,
        "updated": NOW,
        "link": None,
        "locked": False,
        "text": t,
        "fontSize": size,
        "fontFamily": 1,
        "textAlign": "left",
        "verticalAlign": "top",
        "containerId": None,
        "originalText": t,
        "autoResize": True,
        "lineHeight": 1.25,
    }
    elements.append(el)
    return el


def arrow(x: float, y: float, points: list[list[float]], stroke: str = "#334155") -> dict:
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    w = max(xs) - min(xs) if max(xs) != min(xs) else 1.0
    h = max(ys) - min(ys) if max(ys) != min(ys) else 1.0
    el = {
        "id": nid(),
        "type": "arrow",
        "x": x,
        "y": y,
        "width": abs(w),
        "height": abs(h),
        "angle": 0,
        "strokeColor": stroke,
        "backgroundColor": "transparent",
        "fillStyle": "solid",
        "strokeWidth": 2,
        "strokeStyle": "solid",
        "roughness": 0,
        "opacity": 100,
        "groupIds": [],
        "frameId": None,
        "roundness": {"type": 2},
        "seed": seed(),
        "version": 1,
        "versionNonce": seed(),
        "isDeleted": False,
        "boundElements": None,
        "updated": NOW,
        "link": None,
        "locked": False,
        "startBinding": None,
        "endBinding": None,
        "lastCommittedPoint": None,
        "startArrowhead": None,
        "endArrowhead": "arrow",
        "points": points,
    }
    elements.append(el)
    return el


ACCENT = "#0d9488"
SLATE = "#1e293b"
MUTED = "#64748b"
CARD = "#f1f5f9"
WHITE = "#ffffff"
TEAL_SOFT = "#ccfbf1"
AMBER = "#fef3c7"
AMBER_S = "#b45309"
RED_SOFT = "#fee2e2"
GREEN_SOFT = "#dcfce7"

P_W, P_H, GAP = 920, 740, 80

# Panel frames
panel_meta = [
    (0, 0, "1  /  Problem", "GridWise — Campus Energy Optimization"),
    (P_W + GAP, 0, "2  /  Architecture", "LLM → Guardrails → Optimizer → Replay"),
    (
        2 * (P_W + GAP),
        0,
        "3  /  Key Rules",
        "Windows · Solar factor · Neutrality · Reliability",
    ),
]

for px, py, header, subtitle in panel_meta:
    rect(px, py, P_W, P_H, bg=WHITE, stroke="#cbd5e1")
    rect(px + 24, py + 24, P_W - 48, 72, bg=TEAL_SOFT, stroke=ACCENT)
    text(px + 40, py + 36, header, size=22, color=ACCENT)
    text(px + 40, py + 62, subtitle, size=18, color=SLATE)

# ---- Panel 1: Problem ----
px, py = 0, 0
rect(px + 24, py + 114, 520, 40, bg="#e0f2fe", stroke="#0284c7", sw=1)
text(px + 36, py + 122, "Live: https://elec-bup.onrender.com", size=18, color="#0369a1")

rect(px + 310, py + 280, 280, 120, bg=CARD, stroke=SLATE)
text(px + 360, py + 310, "CAMPUS LOAD", size=22, color=SLATE)
text(px + 340, py + 345, "24h demand must be met", size=16, color=MUTED)

sources = [
    (60, 200, "GRID", "priced by hourly tariff", "#fee2e2", "#b91c1c"),
    (60, 320, "SOLAR", "rooftop forecast", "#fef9c3", "#a16207"),
    (60, 440, "BATTERY", "charge / discharge / idle", "#dbeafe", "#1d4ed8"),
]
for sx, sy, title, sub, bg, stroke in sources:
    rect(px + sx, py + sy, 200, 90, bg=bg, stroke=stroke)
    text(px + sx + 16, py + sy + 18, title, size=20, color=stroke)
    text(px + sx + 16, py + sy + 48, sub, size=14, color=MUTED)
    arrow(px + sx + 200, py + sy + 45, [[0, 0], [50, 340 - (sy + 45)]], stroke=stroke)

rect(px + 640, py + 200, 250, 200, bg="#fff7ed", stroke="#ea580c")
text(px + 656, py + 214, "Operator notes", size=18, color="#c2410c")
text(px + 656, py + 244, "1–3 NL strings", size=15, color=MUTED)
text(px + 656, py + 280, "• real constraints", size=15, color=SLATE)
text(px + 656, py + 305, "• distractors → no_op", size=15, color=SLATE)
text(px + 656, py + 340, "API must interpret", size=15, color="#c2410c")
arrow(px + 640, py + 300, [[0, 0], [-50, 40]], stroke="#ea580c")

rect(px + 24, py + 640, P_W - 48, 70, bg=CARD, stroke=SLATE)
text(
    px + 40,
    py + 655,
    "Objective: minimize total_cost_bdt = Σ grid_kwh[h] × tariff[h]",
    size=18,
    color=SLATE,
)
text(
    px + 40,
    py + 682,
    "Keep physics valid: energy balance · battery bounds · EOD neutrality",
    size=15,
    color=MUTED,
)

# ---- Panel 2: Architecture ----
px = P_W + GAP
py = 0
steps = [
    (140, "FastAPI request JSON", "scenario + notes + 24h + battery", CARD, SLATE, "main.py"),
    (
        230,
        "OpenAI gpt-4o-mini",
        "structured JSON interpretation",
        TEAL_SOFT,
        ACCENT,
        "llm.py",
    ),
    (
        320,
        "Guardrails",
        "validate · half-open hour repair",
        AMBER,
        AMBER_S,
        "guardrails.py",
    ),
    (
        410,
        "PuLP / CBC optimizer",
        "minimize grid cost under constraints",
        GREEN_SOFT,
        "#15803d",
        "optimizer.py",
    ),
    (
        500,
        "Replay verifier",
        "balance · battery · directives · EOD",
        "#e0e7ff",
        "#4338ca",
        "replay.py",
    ),
]
bx = px + 80
for sy, title, sub, bg, stroke, fname in steps:
    rect(bx, py + sy, 520, 72, bg=bg, stroke=stroke)
    text(bx + 20, py + sy + 12, title, size=20, color=stroke)
    text(bx + 20, py + sy + 40, sub, size=15, color=MUTED)
    text(bx + 400, py + sy + 24, fname, size=14, color=MUTED)
    if sy < 500:
        arrow(bx + 260, py + sy + 72, [[0, 0], [0, 16]], stroke=SLATE)

rect(px + 620, py + 230, 270, 110, bg="#ecfdf5", stroke=ACCENT)
text(px + 636, py + 246, "LLM on interpretation path", size=16, color=ACCENT)
text(px + 636, py + 275, "Not only plan_summary.", size=15, color=SLATE)
text(px + 636, py + 300, "Mandatory for scoring.", size=15, color=SLATE)

rect(px + 80, py + 600, 520, 56, bg=RED_SOFT, stroke="#b91c1c")
text(
    px + 100,
    py + 616,
    "HTTP 200 only if replay passes — else fail closed",
    size=17,
    color="#b91c1c",
)
text(px + 80, py + 670, "pipeline.py orchestrates end-to-end", size=15, color=MUTED)

# ---- Panel 3: Key rules ----
px = 2 * (P_W + GAP)
py = 0
cards = [
    (
        40,
        130,
        "Half-open windows",
        "1 PM – 3 PM  →  hours [13, 14]",
        "Inclusive start, exclusive end.",
        TEAL_SOFT,
        ACCENT,
    ),
    (
        470,
        130,
        "Solar factor",
        "80% reduction → factor = 0.2",
        "Remaining usable fraction.",
        AMBER,
        AMBER_S,
    ),
    (
        40,
        360,
        "EOD neutrality",
        "SOC after hour 23 = initial SOC",
        "Battery returns to start energy.",
        GREEN_SOFT,
        "#15803d",
    ),
    (
        470,
        360,
        "Reliability extras",
        "retry · note cache · LP relax ladder",
        "Still replay the schedule that solved.",
        "#e0e7ff",
        "#4338ca",
    ),
]
for cx, cy, title, line1, line2, bg, stroke in cards:
    rect(px + cx, py + cy, 400, 200, bg=bg, stroke=stroke)
    text(px + cx + 24, py + cy + 28, title, size=22, color=stroke)
    text(px + cx + 24, py + cy + 80, line1, size=17, color=SLATE, w=350)
    text(px + cx + 24, py + cy + 120, line2, size=15, color=MUTED, w=350)

rect(px + 40, py + 590, 830, 70, bg="#fff7ed", stroke="#ea580c")
text(
    px + 56,
    py + 612,
    "Distractors → directive_type no_op · applies = false",
    size=18,
    color="#c2410c",
)

doc = {
    "type": "excalidraw",
    "version": 2,
    "source": "https://excalidraw.com",
    "elements": elements,
    "appState": {
        "gridSize": None,
        "viewBackgroundColor": "#f8fafc",
        "currentItemStrokeColor": "#1e293b",
        "currentItemBackgroundColor": "#ccfbf1",
        "currentItemFillStyle": "solid",
        "currentItemStrokeWidth": 2,
        "currentItemStrokeStyle": "solid",
        "currentItemRoughness": 0,
        "currentItemOpacity": 100,
        "currentItemFontFamily": 1,
        "currentItemFontSize": 20,
        "currentItemTextAlign": "left",
        "scrollX": 0,
        "scrollY": 0,
        "zoom": {"value": 0.55},
    },
    "files": {},
}

out = Path(__file__).resolve().parent.parent / "docs" / "video-board.excalidraw"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(doc, indent=2), encoding="utf-8")
print(f"wrote {out} ({len(elements)} elements)")
