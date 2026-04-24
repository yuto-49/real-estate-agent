# Tokyo fixture corpus

Frozen local dataset used by unit, integration, and RAG tests for the Tokyo
release. Nothing in this tree should be loaded from the network; every file is
committed so tests are deterministic offline.

## Layout

```
tokyo/
├── reins_samples/        Synthesized REINS listing records (no live REINS data).
├── mlit_transactions/    MLIT 不動産情報ライブラリ 取引価格情報 samples.
├── estat_demographics/   e-Stat 国勢調査 小地域 data samples.
├── hazard_maps/          国土数値情報 ハザード (水害・津波・土砂) GeoJSON samples.
├── zoning/               国土数値情報 用途地域 GeoJSON samples.
├── juuyou_docs/          Placeholder directory for 重要事項説明書 PDF samples.
│                         PDFs must NOT be committed — see SECURITY below.
└── addresses/            Normalized chome-banchi-go address samples.
```

## Provenance

| Source              | Upstream                                                    | License / Use |
|---------------------|-------------------------------------------------------------|---------------|
| REINS samples       | Hand-authored to match published REINS field layout         | synthetic; no redistribution concern |
| MLIT transactions   | https://www.reinfolib.mlit.go.jp/ 取引価格情報 API          | CC-BY 4.0 compatible (confirm at MLIT terms) |
| e-Stat demographics | https://www.e-stat.go.jp/ 国勢調査 小地域                   | 政府標準利用規約 (CC-BY compatible) |
| 国土数値情報         | https://nlftp.mlit.go.jp/ksj/                               | 国土数値情報利用約款 (non-commercial redistribution restricted — check before shipping) |
| Address normalizer  | https://github.com/geolonia/normalize-japanese-addresses    | MIT |

## Synthetic REINS listings

REINS live data MUST NEVER be committed to this repository. Production access is
gated by 宅建業者 membership and redistribution is prohibited. The files in
`reins_samples/` are hand-authored records that match the REINS field schema so
loaders, chunkers, and retrieval tests can run unchanged when live data later
replaces the mock provider.

## 重要事項説明書 PDFs (do not commit)

`juuyou_docs/.gitkeep` is committed; the PDFs themselves are not.
Download the MLIT sample template once per developer:

1. Visit the MLIT 宅建業法 section on the official 国土交通省 site and download
   the current 重要事項説明書ひな形 PDF.
2. Save as `juuyou_docs/jukensetsumei_template.pdf`.
3. The PDF is excluded via `.gitignore`.

Do NOT place any real client's 重説 PDFs here. If a redacted real document is
needed for ingestion tests, strip every personal field first (owner name,
address at banchi-go level, price, contract parties, broker identifiers).

## Data scale

Fixtures are intentionally tiny so the suite stays fast:

- 9 synthetic REINS listings across 3 wards
- ~30 MLIT transactions
- 6 address normalization pairs
- 2 hazard GeoJSON features
- 1 zoning GeoJSON feature collection
- 1 e-Stat population sample

Larger dev data belongs in `scripts/fetch_tokyo_dev_data.py` (not fixtures).
