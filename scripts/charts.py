#!/usr/bin/env python3
"""
Genera i grafici professionali del bollettino a partire da data.json (fetch_forecast.py)
e indices.json (indices.py). Tutti i grafici sono costruiti da dati reali, non stimati.

Uso:
    python3 charts.py data.json indices.json --outdir charts/

Produce nella cartella di output:
    temperature.png   - confronto multi-modello + media
    pressione.png     - confronto multi-modello pressione mslp
    umidita.png        - umidita' relativa (best_match) con banda min/max multimodello
    vento.png          - velocita' e raffiche (best_match) + spread multimodello
    precipitazioni.png - accumulo orario + probabilita'
    cape.png           - CAPE calcolato (MetPy) vs CAPE diretto Open-Meteo, con soglie
    geopotenziale.png  - andamento quota geopotenziale 500/850 hPa
    skewt.png          - diagramma Skew-T/LogP reale per l'istante di CAPE massimo
"""
import argparse
import datetime as dt
import json
import os
import warnings

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.ticker import FuncFormatter
import numpy as np

warnings.filterwarnings("ignore")

PALETTE = {
    "best_match": "#1a1a2e",
}
MODEL_COLORS = ["#4C6EF5", "#F76707", "#37B24D", "#E64980", "#7048E8",
                 "#12B886", "#F59F00", "#1098AD", "#E03131", "#5C7CFA"]

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 10,
    "axes.edgecolor": "#888888",
    "axes.grid": True,
    "grid.alpha": 0.25,
    "grid.linestyle": "--",
    "axes.spines.top": False,
    "axes.spines.right": False,
    "figure.facecolor": "white",
    "axes.facecolor": "white",
})

PROFILE_LEVELS = [1000, 975, 950, 925, 900, 850, 800, 700, 600, 500, 400, 300, 250, 200, 150, 100]

GIORNI_IT = ["lun", "mar", "mer", "gio", "ven", "sab", "dom"]


def parse_times(strs):
    return [dt.datetime.fromisoformat(s) for s in strs]


def _day_label(x, pos=None):
    d = mdates.num2date(x)
    return f"{GIORNI_IT[d.weekday()]} {d.strftime('%d/%m')}"


def fmt_time_axis(ax):
    ax.xaxis.set_major_locator(mdates.DayLocator())
    ax.xaxis.set_major_formatter(FuncFormatter(_day_label))
    ax.xaxis.set_minor_locator(mdates.HourLocator(byhour=[6, 12, 18]))
    ax.xaxis.set_minor_formatter(mdates.DateFormatter("%Hh"))
    ax.tick_params(axis="x", which="minor", labelsize=7, colors="#777777")
    ax.tick_params(axis="x", which="major", labelsize=9, pad=14)


def save(fig, outdir, name):
    path = os.path.join(outdir, name)
    fig.savefig(path, dpi=160, bbox_inches="tight")
    plt.close(fig)
    return path


def chart_multimodel(models, var, title, ylabel, outdir, fname, unit=""):
    fig, ax = plt.subplots(figsize=(9, 4.2))
    best = None
    for i, (mk, mv) in enumerate(models.items()):
        if mv.get("error") or not mv.get("hourly") or var not in mv["hourly"]:
            continue
        times = parse_times(mv["hourly"]["time"])
        vals = mv["hourly"][var]
        if mk == "best_match":
            best = (times, vals)
            continue
        ax.plot(times, vals, color=MODEL_COLORS[i % len(MODEL_COLORS)], linewidth=1.1,
                alpha=0.75, label=mv["label"])
    if best:
        ax.plot(best[0], best[1], color="#1a1a2e", linewidth=2.6, label="Best Match (blend)", zorder=10)
    ax.set_title(title, fontsize=12, fontweight="bold", loc="left")
    ax.set_ylabel(f"{ylabel} ({unit})" if unit else ylabel)
    fmt_time_axis(ax)
    ax.legend(fontsize=7, ncol=2, loc="upper left", bbox_to_anchor=(1.01, 1.0), frameon=False)
    return save(fig, outdir, fname)


def chart_humidity(models, outdir):
    best = models.get("best_match", {})
    if best.get("error") or not best.get("hourly"):
        return None
    times = parse_times(best["hourly"]["time"])
    rh = best["hourly"]["relative_humidity_2m"]

    all_rh = []
    for mv in models.values():
        if not mv.get("error") and mv.get("hourly") and "relative_humidity_2m" in mv["hourly"]:
            arr = mv["hourly"]["relative_humidity_2m"]
            if len(arr) == len(times) and all(x is not None for x in arr):
                all_rh.append(arr)
    rh_min = np.min(all_rh, axis=0) if all_rh else rh
    rh_max = np.max(all_rh, axis=0) if all_rh else rh

    fig, ax = plt.subplots(figsize=(9, 4.0))
    ax.fill_between(times, rh_min, rh_max, color="#4C6EF5", alpha=0.15, label="Spread multi-modello")
    ax.plot(times, rh, color="#1a1a2e", linewidth=2.2, label="Best Match")
    ax.set_title("Umidita' relativa", fontsize=12, fontweight="bold", loc="left")
    ax.set_ylabel("Umidita' relativa (%)")
    ax.set_ylim(0, 100)
    fmt_time_axis(ax)
    ax.legend(fontsize=8, loc="upper left", bbox_to_anchor=(1.01, 1.0), frameon=False)
    return save(fig, outdir, "umidita.png")


def chart_wind(models, outdir):
    best = models.get("best_match", {})
    if best.get("error") or not best.get("hourly"):
        return None
    times = parse_times(best["hourly"]["time"])
    speed = best["hourly"]["wind_speed_10m"]
    gust = best["hourly"]["wind_gusts_10m"]

    fig, ax = plt.subplots(figsize=(9, 4.2))
    for i, (mk, mv) in enumerate(models.items()):
        if mk == "best_match" or mv.get("error") or not mv.get("hourly"):
            continue
        t = parse_times(mv["hourly"]["time"])
        ax.plot(t, mv["hourly"]["wind_speed_10m"], color="#adb5bd", linewidth=0.8, alpha=0.6, zorder=1)
    ax.plot(times, speed, color="#1098AD", linewidth=2.4, label="Vento medio (Best Match)", zorder=5)
    ax.plot(times, gust, color="#E03131", linewidth=1.6, linestyle="--", label="Raffiche (Best Match)", zorder=5)
    ax.set_title("Vento: velocita' e raffiche", fontsize=12, fontweight="bold", loc="left")
    ax.set_ylabel("Nodi (kn)")
    fmt_time_axis(ax)
    ax.legend(fontsize=8, loc="upper left", bbox_to_anchor=(1.01, 1.0), frameon=False)
    return save(fig, outdir, "vento.png")


def chart_precipitation(models, outdir):
    best = models.get("best_match", {})
    if best.get("error") or not best.get("hourly"):
        return None
    times = parse_times(best["hourly"]["time"])
    precip = best["hourly"]["precipitation"]
    prob = best["hourly"].get("precipitation_probability")

    fig, ax = plt.subplots(figsize=(9, 4.2))
    ax.bar(times, precip, width=0.03, color="#4C6EF5", alpha=0.85, label="Precipitazione (mm/h)")
    ax.set_ylabel("mm/h")
    ax.set_title("Precipitazioni previste", fontsize=12, fontweight="bold", loc="left")
    fmt_time_axis(ax)
    if prob:
        ax2 = ax.twinx()
        ax2.plot(times, prob, color="#F76707", linewidth=2, label="Probabilita' (%)")
        ax2.set_ylabel("Probabilita' (%)")
        ax2.set_ylim(0, 100)
        ax2.grid(False)
        lines1, labels1 = ax.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax.legend(lines1 + lines2, labels1 + labels2, fontsize=8, loc="upper left",
                  bbox_to_anchor=(1.05, 1.0), frameon=False)
    return save(fig, outdir, "precipitazioni.png")


def chart_cape(indices, best_hourly, outdir):
    steps = indices.get("timesteps")
    if not steps:
        return None
    times = parse_times([s["time"] for s in steps])
    sbcape = [s.get("sbcape_Jkg") for s in steps]
    cape_om = [s.get("cape_openmeteo_Jkg") for s in steps]

    fig, ax = plt.subplots(figsize=(9, 4.2))
    ax.plot(times, sbcape, color="#1a1a2e", linewidth=2.2, label="SBCAPE calcolato (MetPy)")
    ax.plot(times, cape_om, color="#F76707", linewidth=1.6, linestyle="--", label="CAPE diretto (Open-Meteo)")
    for th, lbl, col in [(500, "debole", "#ffd43b"), (1500, "moderato", "#ff922b"), (2500, "forte", "#e03131")]:
        ax.axhline(th, color=col, linewidth=0.8, alpha=0.6)
        ax.text(times[-1], th, f" {lbl}", fontsize=7, va="center", color=col)
    ax.set_ylabel("CAPE (J/kg)")
    ax.set_title("CAPE (energia potenziale convettiva disponibile)", fontsize=12, fontweight="bold", loc="left")
    fmt_time_axis(ax)
    ax.legend(fontsize=8, loc="upper left", bbox_to_anchor=(1.01, 1.0), frameon=False)
    return save(fig, outdir, "cape.png")


def chart_geopotential(profile, outdir):
    hourly = profile.get("hourly")
    if not hourly:
        return None
    times = parse_times(hourly["time"])
    g500 = hourly.get("geopotential_height_500hPa")
    g850 = hourly.get("geopotential_height_850hPa")
    if not g500 or not g850:
        return None

    fig, ax1 = plt.subplots(figsize=(9, 4.0))
    ax1.plot(times, g500, color="#1a1a2e", linewidth=2.2, label="Quota geopotenziale 500 hPa")
    ax1.set_ylabel("500 hPa (m)")
    ax2 = ax1.twinx()
    ax2.plot(times, g850, color="#4C6EF5", linewidth=2.0, linestyle="--", label="Quota geopotenziale 850 hPa")
    ax2.set_ylabel("850 hPa (m)")
    ax2.grid(False)
    ax1.set_title("Geopotenziale 500 hPa e 850 hPa", fontsize=12, fontweight="bold", loc="left")
    fmt_time_axis(ax1)
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, fontsize=8, loc="upper left",
               bbox_to_anchor=(1.01, 1.0), frameon=False)
    return save(fig, outdir, "geopotenziale.png")


def chart_skewt(profile, indices, outdir):
    from metpy.plots import SkewT
    from metpy.units import units
    import metpy.calc as mpcalc

    hourly = profile.get("hourly")
    if not hourly:
        return None
    steps = indices.get("timesteps", [])
    if not steps:
        idx = len(hourly["time"]) // 2
    else:
        capes = [s.get("sbcape_Jkg") or 0 for s in steps]
        # Preferisci l'ora di massima instabilita' nella finestra diurna (10-19 locali),
        # piu' rilevante per la convezione pomeridiana; ricadi sul massimo assoluto
        # solo se non c'e' alcun dato diurno disponibile.
        daytime_idx = [i for i, s in enumerate(steps)
                       if 10 <= dt.datetime.fromisoformat(s["time"]).hour <= 19]
        if daytime_idx:
            idx = max(daytime_idx, key=lambda i: capes[i])
        else:
            idx = int(np.argmax(capes))

    t_dt = dt.datetime.fromisoformat(hourly["time"][idx])
    t_label = f"{GIORNI_IT[t_dt.weekday()]} {t_dt.strftime('%d/%m %H:%M')}"
    pressures, temps, rhs, wspd, wdir = [], [], [], [], []
    for lvl in PROFILE_LEVELS:
        t = hourly.get(f"temperature_{lvl}hPa", [None])[idx]
        rh = hourly.get(f"relative_humidity_{lvl}hPa", [None])[idx]
        ws = hourly.get(f"wind_speed_{lvl}hPa", [None])[idx]
        wd = hourly.get(f"wind_direction_{lvl}hPa", [None])[idx]
        if None in (t, rh, ws, wd):
            continue
        pressures.append(lvl)
        temps.append(t)
        rhs.append(rh)
        wspd.append(ws)
        wdir.append(wd)

    if len(pressures) < 6:
        return None

    p = np.array(pressures) * units.hPa
    T = np.array(temps) * units.degC
    Td = mpcalc.dewpoint_from_relative_humidity(T, np.array(rhs) * units.percent)
    u, v = mpcalc.wind_components((np.array(wspd) * units.knots), np.array(wdir) * units.deg)

    fig = plt.figure(figsize=(7, 8))
    skew = SkewT(fig, rotation=45)
    skew.plot(p, T, "r", linewidth=2, label="Temperatura")
    skew.plot(p, Td, "g", linewidth=2, label="Punto di rugiada")
    skew.plot_barbs(p, u, v)
    skew.ax.set_ylim(1000, 100)
    skew.ax.set_xlim(-40, 40)
    skew.plot_dry_adiabats(linewidth=0.5, alpha=0.4)
    skew.plot_moist_adiabats(linewidth=0.5, alpha=0.4)
    skew.plot_mixing_lines(linewidth=0.5, alpha=0.4)
    try:
        parcel = mpcalc.parcel_profile(p, T[0], Td[0])
        skew.plot(p, parcel, "k", linewidth=1.5, linestyle="--", label="Profilo parcella")
        skew.shade_cape(p, T, parcel)
        skew.shade_cin(p, T, parcel, Td)
    except Exception:
        pass
    skew.ax.set_title(f"Skew-T / Log-P - {t_label}", fontsize=12, fontweight="bold")
    skew.ax.legend(fontsize=8, loc="upper right")
    return save(fig, outdir, "skewt.png")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("data_json")
    ap.add_argument("indices_json")
    ap.add_argument("--outdir", required=True)
    args = ap.parse_args()
    os.makedirs(args.outdir, exist_ok=True)

    with open(args.data_json, encoding="utf-8") as f:
        data = json.load(f)
    with open(args.indices_json, encoding="utf-8") as f:
        indices = json.load(f)

    models = data["models"]
    produced = {}
    produced["temperatura"] = chart_multimodel(models, "temperature_2m", "Temperatura a 2m - confronto modelli",
                                                "Temperatura", args.outdir, "temperatura.png", "C")
    produced["pressione"] = chart_multimodel(models, "pressure_msl", "Pressione al livello del mare - confronto modelli",
                                              "Pressione", args.outdir, "pressione.png", "hPa")
    produced["umidita"] = chart_humidity(models, args.outdir)
    produced["vento"] = chart_wind(models, args.outdir)
    produced["precipitazioni"] = chart_precipitation(models, args.outdir)
    produced["cape"] = chart_cape(indices, models.get("best_match", {}).get("hourly"), args.outdir)
    produced["geopotenziale"] = chart_geopotential(data.get("profile", {}), args.outdir)
    try:
        produced["skewt"] = chart_skewt(data.get("profile", {}), indices, args.outdir)
    except Exception as e:
        produced["skewt"] = None
        print(f"Skew-T non generato: {e}")

    manifest_path = os.path.join(args.outdir, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(produced, f, ensure_ascii=False, indent=2)

    for k, v in produced.items():
        print(f"{k}: {'OK -> ' + v if v else 'NON GENERATO'}")


if __name__ == "__main__":
    main()
