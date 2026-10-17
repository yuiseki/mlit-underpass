# mlit-underpass

Reproducible collection of the national underpass map (全国のアンダーパス箇所マップ) of the
Ministry of Land, Infrastructure, Transport and Tourism (国土交通省 道路局): 3,841 points of road
sections that are much lower than the sections before and after them. One GeoParquet for all of
Japan and one per prefecture. This repository holds the code; the data is on the Hub:
<https://huggingface.co/datasets/yuiseki/mlit-underpass>

## Source and licence

- Map page: <https://www.mlit.go.jp/road/saigai/underpass/map/map.html> (loads 10 GeoJSON blocks);
  index page: <https://www.mlit.go.jp/road/road_fr4_000208.html>.
- Terms: MLIT site terms, <https://www.mlit.go.jp/link.html>, Public Data License 1.0, which is
  compatible with CC BY 4.0. The data is offered under CC BY 4.0; the dataset card
  (`data/README.md`, uploaded to the Hub) has the credit line, the changes and the known issues.
- The code in this repository is MIT (see `LICENSE`).

## Running it

```sh
uv venv && uv pip install pyarrow shapely huggingface-hub pytest ruff
python3 scripts/01_download.py      # 10 blocks, sequential, 1 s apart; data/raw/<date>/MANIFEST.json
python3 scripts/02_export_parquet.py # needs prefectures.parquet of yuiseki/jp-admin-2026-09 (--admin)
python3 scripts/03_verify.py        # parquet against the downloaded blocks
python3 scripts/04_card.py          # data/README.md, LICENSE, provenance.yaml
python3 src/publish.py              # dry run; --push to upload
.venv/bin/python -m pytest
```

The source overwrites its map in place, so the Hub holds the newest run only.
