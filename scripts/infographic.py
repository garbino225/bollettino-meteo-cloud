#!/usr/bin/env python3
"""
Genera l'infografica riassuntiva del bollettino: card giornaliere (icona, temperature,
vento, pioggia), tabella rischi colorata e indicatore di affidabilita'.

I dati numerici (temperature, vento, pioggia, icona) vengono letti direttamente da
data.json (best_match, valori giornalieri reali). I livelli di rischio e l'affidabilita'
sono un giudizio professionale e vanno forniti dall'agente in un file content.json
dopo aver completato l'analisi sinottica e convettiva.

Uso:
    python3 infographic.py data.json content.json --out infografica.png

Formato content.json atteso:
{
  "location_label": "Rimini (RN)",
  "period_label": "23-26 luglio 2026",
  "reliability_pct": 85,
  "reliability_note": "Buon accordo tra i modelli sulla traiettoria della saccatura",
  "risks": {"Temporali": "Medio", "Grandine": "Basso", "Vento": "Basso",
            "Pioggia intensa": "Medio", "Caldo": "Alto", "Freddo": "Basso",
            "Nebbia": "Basso", "Mare": "Basso"}
}
"""
import argparse
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Ellipse, FancyBboxPatch, Polygon, Wedge
import numpy as np

RISK_COLORS = {"Basso": "#37B24D", "Medio": "#F59F00", "Alto": "#E03131"}
BG = "#F8F9FA"


def weather_icon_kind(code):
    if code is None:
        return "cloud"
    if code == 0:
        return "sun"
    if code in (1, 2):
        return "partly"
    if code == 3:
        return "cloud"
    if code in (45, 48):
        return "fog"
    if code in (71, 73, 75, 77, 85, 86):
        return "snow"
    if code in (95, 96, 99):
        return "storm"
    if code in (51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82):
        return "rain"
    return "cloud"


def draw_icon(ax, kind, cx=0.5, cy=0.62, scale=1.6):
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    def cloud(cx, cy, s=1.55, color="#adb5bd"):
        for dx, dy, r in [(-0.16, 0, 0.14), (0, 0.05, 0.17), (0.17, 0, 0.13), (0, -0.06, 0.16)]:
            ax.add_patch(Ellipse((cx + dx * s, cy + dy * s), 0.32 * r / 0.14 * s * 0.5, 0.22 * r / 0.14 * s * 0.5,
                                  color=color, zorder=3))

    if kind == "sun":
        ax.add_patch(Circle((cx, cy), 0.16 * scale, color="#F59F00", zorder=3))
        for ang in np.linspace(0, 2 * np.pi, 12, endpoint=False):
            x0, y0 = cx + 0.20 * scale * np.cos(ang), cy + 0.20 * scale * np.sin(ang)
            x1, y1 = cx + 0.30 * scale * np.cos(ang), cy + 0.30 * scale * np.sin(ang)
            ax.plot([x0, x1], [y0, y1], color="#F59F00", linewidth=2, zorder=3)
    elif kind == "partly":
        ax.add_patch(Circle((cx - 0.1, cy + 0.08), 0.13 * scale, color="#F59F00", zorder=2))
        cloud(cx + 0.05, cy - 0.05, s=0.9)
    elif kind == "fog":
        cloud(cx, cy + 0.1, s=0.8, color="#ced4da")
        for i, yy in enumerate([0.28, 0.20, 0.12]):
            ax.plot([cx - 0.28, cx + 0.28], [yy, yy], color="#adb5bd", linewidth=3, alpha=0.8, zorder=3)
    elif kind == "snow":
        cloud(cx, cy + 0.08, s=0.85)
        for dx in (-0.15, 0, 0.15):
            ax.text(cx + dx, cy - 0.18, "*", ha="center", va="center", fontsize=18, color="#4dabf7", zorder=4)
    elif kind == "storm":
        cloud(cx, cy + 0.1, s=0.9, color="#868e96")
        bolt = Polygon([(cx + 0.03, cy - 0.05), (cx - 0.07, cy - 0.22), (cx, cy - 0.20),
                        (cx - 0.05, cy - 0.36), (cx + 0.10, cy - 0.14), (cx + 0.01, cy - 0.16)],
                       closed=True, color="#F59F00", zorder=4)
        ax.add_patch(bolt)
    elif kind == "rain":
        cloud(cx, cy + 0.1, s=0.9)
        for dx in (-0.14, 0.0, 0.14):
            ax.plot([cx + dx, cx + dx - 0.04], [cy - 0.12, cy - 0.28], color="#4C6EF5", linewidth=2.2, zorder=4)
    else:
        cloud(cx, cy)


def day_card(ax, day_label, tmax, tmin, precip, prob, gust, icon_kind):
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    ax.add_patch(FancyBboxPatch((0.03, 0.03), 0.94, 0.94, boxstyle="round,pad=0,rounding_size=0.06",
                                 linewidth=1, edgecolor="#dee2e6", facecolor="white", zorder=1))
    ax.text(0.5, 0.93, day_label, ha="center", va="top", fontsize=11, fontweight="bold", color="#1a1a2e")
    icon_ax = ax.inset_axes([0.2, 0.42, 0.6, 0.42])
    draw_icon(icon_ax, icon_kind)
    tmax_s = f"{tmax:.0f}°" if tmax is not None else "--"
    tmin_s = f"{tmin:.0f}°" if tmin is not None else "--"
    ax.text(0.5, 0.40, f"{tmax_s} / {tmin_s}", ha="center", va="top", fontsize=13, fontweight="bold",
            color="#1a1a2e")
    precip_s = f"{precip:.0f}mm" if precip else "0mm"
    prob_s = f"{prob:.0f}%" if prob is not None else "-"
    ax.text(0.5, 0.24, f"🌧 {precip_s}  ({prob_s})".replace("🌧 ", ""), ha="center", va="top", fontsize=9,
            color="#4C6EF5")
    gust_s = f"{gust:.0f}kn" if gust is not None else "-"
    ax.text(0.5, 0.13, f"vento raffiche max {gust_s}", ha="center", va="top", fontsize=8, color="#495057")


def reliability_gauge(ax, pct):
    ax.set_xlim(-1.35, 1.35)
    ax.set_ylim(-0.2, 1.2)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.add_patch(Wedge((0, 0), 1, 0, 180, width=0.25, facecolor="#e9ecef"))
    color = "#37B24D" if pct >= 80 else ("#F59F00" if pct >= 60 else "#E03131")
    ax.add_patch(Wedge((0, 0), 1, 180 - 180 * (pct / 100), 180, width=0.25, facecolor=color))
    ax.text(0, 0.15, f"{pct:.0f}%", ha="center", va="center", fontsize=20, fontweight="bold", color="#1a1a2e")
    ax.text(0, -0.05, "AFFIDABILITA'", ha="center", va="center", fontsize=9, color="#495057")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("data_json")
    ap.add_argument("content_json")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    with open(args.data_json, encoding="utf-8") as f:
        data = json.load(f)
    with open(args.content_json, encoding="utf-8") as f:
        content = json.load(f)

    best = data["models"].get("best_match", {})
    daily = best.get("daily", {}) or {}
    days = daily.get("time", [])
    n_days = min(len(days), 6)

    risks = content.get("risks", {})
    n_risks = max(len(risks), 1)

    fig = plt.figure(figsize=(11.5, 3.2 + 0.6 * ((n_risks + 3) // 4)), facecolor=BG)
    n_cols = max(n_days, 1)
    gs = fig.add_gridspec(3, n_cols, height_ratios=[0.5, 2.0, 1.3], hspace=0.55, wspace=0.12)

    title_ax = fig.add_subplot(gs[0, :])
    title_ax.axis("off")
    title_ax.text(0, 0.7, f"{content.get('location_label', '')}", fontsize=16, fontweight="bold", color="#1a1a2e")
    title_ax.text(0, 0.05, f"{content.get('period_label', '')}", fontsize=11, color="#495057")

    for i in range(n_days):
        ax = fig.add_subplot(gs[1, i])
        wcode = daily.get("weather_code", [None] * n_days)[i]
        day_card(
            ax,
            days[i][5:] if len(days[i]) > 5 else days[i],
            daily.get("temperature_2m_max", [None] * n_days)[i],
            daily.get("temperature_2m_min", [None] * n_days)[i],
            daily.get("precipitation_sum", [None] * n_days)[i],
            daily.get("precipitation_probability_max", [None] * n_days)[i],
            daily.get("wind_gusts_10m_max", [None] * n_days)[i],
            weather_icon_kind(wcode),
        )

    risk_ax = fig.add_subplot(gs[2, :n_cols - 1] if n_cols > 1 else gs[2, :])
    risk_ax.set_xlim(0, 1)
    risk_ax.set_ylim(0, 1)
    risk_ax.axis("off")
    items = list(risks.items())
    n_row = 4
    for idx, (name, level) in enumerate(items):
        row = idx // n_row
        col = idx % n_row
        x0 = col / n_row + 0.01
        y0 = 0.85 - row * 0.42
        color = RISK_COLORS.get(level, "#adb5bd")
        risk_ax.add_patch(FancyBboxPatch((x0, y0 - 0.28), 1 / n_row - 0.03, 0.30,
                                          boxstyle="round,pad=0,rounding_size=0.04",
                                          facecolor=color, alpha=0.15, edgecolor=color, linewidth=1.4))
        risk_ax.text(x0 + 0.01, y0 - 0.03, name, fontsize=9, fontweight="bold", color="#1a1a2e", va="top")
        risk_ax.text(x0 + 0.01, y0 - 0.18, level, fontsize=10, color=color, fontweight="bold", va="top")

    if n_cols > 1:
        gauge_ax = fig.add_subplot(gs[2, n_cols - 1])
        reliability_gauge(gauge_ax, content.get("reliability_pct", 70))
    else:
        gauge_ax = fig.add_axes([0.75, 0.02, 0.2, 0.3])
        reliability_gauge(gauge_ax, content.get("reliability_pct", 70))

    fig.savefig(args.out, dpi=160, bbox_inches="tight", pad_inches=0.25, facecolor=BG)
    plt.close(fig)
    print(f"OK -> {args.out}")


if __name__ == "__main__":
    main()
