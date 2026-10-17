"""Download the underpass map of MLIT: the 10 GeoJSON blocks the map page loads.

The page (map/map.html) names the blocks; each is fetched once, sequentially, one second apart
(403 or 429 stops the run), hashed and recorded in data/raw/<version>/MANIFEST.json with the
Last-Modified the server states. The page and the index page are saved under docs/ so the
licence and the dates can be read back. The version is the UTC date of the first run.

    uv run python scripts/01_download.py [--version 2026-10-17]
"""

import argparse
import datetime as dt
import hashlib
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import underpass as u

ROOT = Path(__file__).parents[1]
UA = "mlit-underpass/0.1 (+https://github.com/yuiseki/mlit-underpass)"


def get(url: str) -> tuple[bytes, dict[str, str]]:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.read(), {k.lower(): v for k, v in r.headers.items()}
    except urllib.error.HTTPError as e:
        if e.code in (403, 429):
            raise SystemExit(f"{e.code} from {url}: stopping") from e
        raise


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", default=dt.datetime.now(dt.UTC).strftime("%Y-%m-%d"))
    a = ap.parse_args()
    raw = ROOT / "data" / "raw" / a.version
    docs = ROOT / "data" / "docs"
    raw.mkdir(parents=True, exist_ok=True)
    docs.mkdir(parents=True, exist_ok=True)
    page, ph = get(u.PAGE_URL)
    (docs / "map.html").write_bytes(page)
    idx, ih = get(u.INDEX_URL)
    (docs / "road_fr4_000208.html").write_bytes(idx)
    paths = u.parse_blocks(page.decode("utf-8"))
    files = {}
    for p in paths:
        time.sleep(1)
        body, h = get(u.BASE + p)
        (raw / Path(p).name).write_bytes(body)
        files[Path(p).name] = {
            "url": u.BASE + p,
            "bytes": len(body),
            "sha256": hashlib.sha256(body).hexdigest(),
            "last_modified": h.get("last-modified"),
            "block": u.block_of(p),
        }
        print(f"{Path(p).name}: {len(body):,} bytes, {h.get('last-modified')}", flush=True)
    manifest = {
        "version": a.version,
        "fetched_at": dt.datetime.now(dt.UTC).isoformat(),
        "page_url": u.PAGE_URL,
        "page_last_modified": ph.get("last-modified"),
        "index_url": u.INDEX_URL,
        "index_last_modified": ih.get("last-modified"),
        "files": files,
    }
    (raw / "MANIFEST.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
