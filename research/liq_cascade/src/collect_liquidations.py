#!/usr/bin/env python3
"""
Binance USDS-M Futures — forceOrder WebSocket collector.

Subscribes to the all-market liquidation stream and stores events for
BTCUSDT and ETHUSDT to append-only CSVs in ../data/.

Binance stream note: the exchange pushes only the largest single liquidation
order per 1000ms window per symbol. Multiple simultaneous liquidations within
one second appear as one event sized to the largest order. This means large
cascades show as single high-notional events, which is exactly what the gate
threshold is designed to capture.

Run continuously; auto-reconnects with exponential back-off on disconnect.
Safe to restart at any time — CSV files are append-only and restart-safe.
"""

import asyncio
import csv
import json
import logging
import signal
import sys
from datetime import datetime, timezone
from pathlib import Path

import websockets

# ── paths ────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
LOG_FILE = DATA_DIR / "collector.log"

# ── config ───────────────────────────────────────────────────────────────────
# All-market liquidation stream: one message per largest liq per 1000ms per symbol
WS_URL = "wss://fstream.binance.com/ws/!forceOrder@arr"

# Only write rows for these symbols; other symbols are silently dropped
SYMBOLS = {"BTCUSDT", "ETHUSDT"}

CSV_HEADER = [
    "event_time_ms",    # Binance event timestamp (ms since epoch)
    "trade_time_ms",    # Trade execution timestamp from Binance (ms)
    "symbol",
    "side",             # SELL = long-side liquidation (engine sold), BUY = short-side
    "order_price",      # The limit price the engine posted
    "avg_fill_price",   # Actual average fill price (ap field)
    "orig_qty",         # Original order quantity (base asset)
    "fill_qty",         # Quantity actually filled
    "notional_usd",     # fill_qty × avg_fill_price  (approximate USD value)
    "status",           # FILLED or PARTIALLY_FILLED
    "collected_at_utc", # Wall-clock UTC ISO timestamp when we wrote this row
]

RECONNECT_BASE = 5   # seconds before first reconnect attempt
RECONNECT_MAX  = 60  # cap on back-off delay

# ── logging ──────────────────────────────────────────────────────────────────
DATA_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("liq_collector")


# ── CSV helpers ───────────────────────────────────────────────────────────────

def _csv_path(symbol: str) -> Path:
    return DATA_DIR / f"events_{symbol}.csv"


def _ensure_header(path: Path) -> None:
    """Write the header row if the file doesn't exist or is empty."""
    if not path.exists() or path.stat().st_size == 0:
        with open(path, "w", newline="") as f:
            csv.writer(f).writerow(CSV_HEADER)


def _write_event(msg: dict) -> None:
    """Parse a forceOrder message and append one row to the symbol CSV."""
    o = msg["o"]
    sym = o["s"]
    if sym not in SYMBOLS:
        return

    fill_qty = float(o.get("z") or o.get("l") or o["q"])
    avg_price = float(o["ap"]) if o.get("ap") else float(o["p"])
    notional = round(fill_qty * avg_price, 2)

    row = [
        msg["E"],                              # event_time_ms
        o["T"],                                # trade_time_ms
        sym,
        o["S"],                                # side
        o["p"],                                # order_price
        o.get("ap", o["p"]),                   # avg_fill_price
        o["q"],                                # orig_qty
        fill_qty,
        notional,
        o["X"],                                # status
        datetime.now(timezone.utc).isoformat(),
    ]
    path = _csv_path(sym)
    with open(path, "a", newline="") as f:
        csv.writer(f).writerow(row)


# ── WebSocket loop ────────────────────────────────────────────────────────────

async def _collect() -> None:
    delay = RECONNECT_BASE
    total_events = 0

    while True:
        try:
            log.info("Connecting to %s", WS_URL)
            async with websockets.connect(
                WS_URL,
                ping_interval=20,
                ping_timeout=30,
                open_timeout=15,
            ) as ws:
                delay = RECONNECT_BASE
                log.info("Connected. Listening for BTCUSDT / ETHUSDT liquidations.")
                async for raw in ws:
                    msg = json.loads(raw)
                    if msg.get("e") == "forceOrder":
                        _write_event(msg)
                        total_events += 1
                        if total_events % 50 == 0:
                            log.info("Events recorded so far: %d", total_events)

        except (websockets.exceptions.ConnectionClosed, OSError) as exc:
            log.warning("Disconnected (%s) — retrying in %ds", exc, delay)
            await asyncio.sleep(delay)
            delay = min(delay * 2, RECONNECT_MAX)

        except Exception as exc:
            log.error("Unexpected error: %s", exc, exc_info=True)
            await asyncio.sleep(delay)
            delay = min(delay * 2, RECONNECT_MAX)


def _shutdown(signum, frame):
    log.info("Received signal %d — shutting down.", signum)
    sys.exit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    for sym in SYMBOLS:
        _ensure_header(_csv_path(sym))
    log.info("Liquidation collector starting. Symbols: %s", sorted(SYMBOLS))
    log.info("Data directory: %s", DATA_DIR)

    asyncio.run(_collect())
