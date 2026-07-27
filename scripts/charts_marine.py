#!/usr/bin/env python3
"""
Genera i grafici mare (onda multi-modello + marea) del bollettino a partire
da marine.json (fetch_marine.py). Stesso stile grafico di charts.py, dati reali.

Uso:
    python3 charts_marine.py marine.json --outdir charts/

Produce nella cartella di output:
    onda.png   - altezza onda (confronto multi-modello) + periodo e direzione (best_match)
    marea.png  - livello del mare (marea) con alta/bassa marea marcate
"""
import argparse
import datetime as dt
import json
import os
import warnings

import numpy as np

from charts import parse_times, fmt_time_axis, save, MODEL_COLORS, GIORNI_IT

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

warnings.filterwarnings("ignore")


def chart_wave(wave_models, outdir):
    best = wave_models.get("best_match", {})
    if best.get("error") or not best.get("hourly"):
        return None
    times = parse_times(best["hourly"]["time"])
    height = best["hourly"]["wave_height"]
    period = best["hourly"]["wave_period"]
    direction = best["hourly"]["wave_direction"]

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(9, 6.4), sharex=True,
                                    gridspec_kw={"height_ratios": [1.3, 1]})

    for i, (mk, mv) in enumerate(wave_models.items()):
        if mk == "best_match" or mv.get("error") or not mv.get("hourly"):
            continue
        t = parse_times(mv["hourly"]["time"])
        ax1.plot(t, mv["hourly"]["wave_height"], color=MODEL_COLORS[i % len(MODEL_COLORS)],
                  linewidth=1.0, alpha=0.7, label=mv["label"])
    ax1.plot(times, height, color="#1a1a2e", linewidth=2.6, label="Best Match (blend)", zorder=10)
    ax1.set_title("Onda: altezza - confronto modelli", fontsize=12, fontweight="bold", loc="left")
    ax1.set_ylabel("Altezza onda (m)")
    ax1.legend(fontsize=7, ncol=2, loc="upper left", bbox_to_anchor=(1.01, 1.0), frameon=False)

    ax2.plot(times, period, color="#1098AD", linewidth=2.0, label="Periodo onda (Best Match)")
    ax2.set_ylabel("Periodo (s)")
    ax2.set_title("Onda: periodo e direzione (frecce = provenienza, ogni 3h)",
                   fontsize=11, fontweight="bold", loc="left")

    step = 3
    idxs = list(range(0, len(times), step))
    xs = [times[i] for i in idxs]
    ys = [period[i] for i in idxs]
    dirs = [direction[i] for i in idxs]
    rad = np.radians(dirs)
    # Meteorologicamente la direzione e' quella di PROVENIENZA dell'onda:
    # la freccia punta verso dove l'onda si dirige (direzione + 180 gradi).
    u = np.sin(rad + np.pi)
    v = np.cos(rad + np.pi)
    xnum = matplotlib.dates.date2num(xs)
    ax2.quiver(xnum, ys, u, v, color="#E64980", scale=18, width=0.005,
               pivot="mid", zorder=10, label="Direzione onda (verso cui si dirige)")

    ax2.legend(fontsize=7, loc="upper left", bbox_to_anchor=(1.01, 1.0), frameon=False)
    fmt_time_axis(ax2)
    return save(fig, outdir, "onda.png")


def chart_tide(tide, outdir):
    if tide.get("error") or not tide.get("hourly"):
        return None
    hourly = tide["hourly"]
    times = parse_times(hourly["time"])
    level = hourly["sea_level_height_msl"]
    if any(v is None for v in level):
        return None

    level = np.array(level)
    # Estremi locali (alta/bassa marea): confronto con i vicini immediati sui dati orari.
    extrema = []
    for i in range(1, len(level) - 1):
        if level[i] > level[i - 1] and level[i] >= level[i + 1]:
            extrema.append((i, "alta"))
        elif level[i] < level[i - 1] and level[i] <= level[i + 1]:
            extrema.append((i, "bassa"))

    fig, ax = plt.subplots(figsize=(9, 4.2))
    ax.plot(times, level, color="#1a1a2e", linewidth=2.2)
    ax.fill_between(times, level, min(level) - 0.1, color="#4C6EF5", alpha=0.12)
    for i, kind in extrema:
        color = "#E03131" if kind == "alta" else "#1098AD"
        ax.plot(times[i], level[i], "o", color=color, markersize=6, zorder=10)
        ax.annotate(f"{kind}\n{times[i].strftime('%Hh')}", (times[i], level[i]),
                    textcoords="offset points", xytext=(0, 10 if kind == "alta" else -22),
                    fontsize=7, ha="center", color=color, fontweight="bold")
    ax.set_title("Marea (livello del mare, incl. componente astronomica)",
                  fontsize=12, fontweight="bold", loc="left")
    ax.set_ylabel("Livello sul medio mare (m)")
    ymin, ymax = ax.get_ylim()
    ax.set_ylim(ymin, ymax + 0.22 * (ymax - ymin))
    fmt_time_axis(ax)
    return save(fig, outdir, "marea.png")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("marine_json")
    ap.add_argument("--outdir", required=True)
    args = ap.parse_args()
    os.makedirs(args.outdir, exist_ok=True)

    with open(args.marine_json, encoding="utf-8") as f:
        marine = json.load(f)

    produced = {}
    produced["onda"] = chart_wave(marine.get("wave_models", {}), args.outdir)
    produced["marea"] = chart_tide(marine.get("tide", {}), args.outdir)

    manifest_path = os.path.join(args.outdir, "manifest_marine.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(produced, f, ensure_ascii=False, indent=2)

    for k, v in produced.items():
        print(f"{k}: {'OK -> ' + v if v else 'NON GENERATO'}")


if __name__ == "__main__":
    main()
