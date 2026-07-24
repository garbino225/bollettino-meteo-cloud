#!/usr/bin/env python3
"""
Invia un PDF (o un messaggio di testo semplice) al relay Cloudflare Worker
che inoltra su Telegram. Il vero bot token vive solo nel secret store del
Worker: questo script non lo vede mai, usa solo il RELAY_SECRET (chiave
anti-abuso, non il token Telegram) passato come argomento.

Uso:
    python3 relay_send.py --url https://tuo-worker.workers.dev --secret RELAY_SECRET \
        --pdf bollettino.pdf --caption "Bollettino Imola - 24/07/2026"

    python3 relay_send.py --url https://tuo-worker.workers.dev --secret RELAY_SECRET \
        --message "Testo semplice"
"""
import argparse
import os
import sys
import requests


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True, help="URL del Cloudflare Worker relay")
    ap.add_argument("--secret", default=os.environ.get("RELAY_SECRET"),
                     help="Valore di X-Relay-Secret (default: variabile d'ambiente RELAY_SECRET)")
    ap.add_argument("--pdf", help="Percorso del PDF da inviare come documento")
    ap.add_argument("--message", help="Testo semplice da inviare (alternativo a --pdf)")
    ap.add_argument("--caption", default="", help="Didascalia per il documento PDF")
    args = ap.parse_args()

    if not args.secret:
        print("Serve --secret o la variabile d'ambiente RELAY_SECRET", file=sys.stderr)
        sys.exit(1)

    headers = {"X-Relay-Secret": args.secret}

    if args.pdf:
        with open(args.pdf, "rb") as f:
            files = {"document": (os.path.basename(args.pdf), f, "application/pdf")}
            data = {"caption": args.caption} if args.caption else {}
            r = requests.post(args.url, headers=headers, files=files, data=data, timeout=120)
    elif args.message:
        r = requests.post(args.url, headers=headers, json={"message": args.message}, timeout=30)
    else:
        print("Serve --pdf o --message", file=sys.stderr)
        sys.exit(1)

    print(r.status_code, r.text[:500])
    if r.status_code != 200:
        sys.exit(1)


if __name__ == "__main__":
    main()
