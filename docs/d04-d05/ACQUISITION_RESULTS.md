# D04 acquisition results — 28 November 2026

Actual source files were acquired in GitHub Actions. No nationwide downloads.

| Pilot | Source | Municipal extracts | Downloaded archive bytes | Water polygons | Original line features | Polygon holes after finalization |
|---|---|---:|---:|---:|---:|---:|
| Oslo–Lillestrøm | N50 CC BY 4.0 | 12 | 48,403,638 | 429 | 1,972 | 209 |
| Aurland | N50 CC BY 4.0 | 3 | 48,446,780 | 483 | 1,012 | 28 |
| Herning | Overture base ODbL 1.0 | n/a | Not measured (range query) | 704 | 655 | 10 |

- [Norwegian acquisition run](https://github.com/ruishinor/nordicciv/actions/runs/46181266975), [Oslo artifact](https://github.com/ruishinor/nordicciv/actions/runs/46181266975/artifacts/15278215141), [Aurland artifact](https://github.com/ruishinor/nordicciv/actions/runs/46181266975/artifacts/15277302574).
- [Herning fallback run](https://github.com/ruishinor/nordicciv/actions/runs/46181344653), [Herning ODbL artifact](https://github.com/ruishinor/nordicciv/actions/runs/46181344653/artifacts/15277538543).
- Original run reports include exact source archive names, dates of acquisition, hashes, layer names and feature counts. N50 actual layers: N50_Arealdekke_omrade and N50_Arealdekke_senterlinje. Source classes: elv, havflate, innsjø, innsjøregulert and elvbekk.
- All six acquired output files and both Herning selected source files matched reported hashes after download. One Oslo polygon had a self-intersection after WGS84 export; repaired by finalization, and clip now revalidates after inverse projection. No redownload. All finalized geometries valid, within pilot (maximum numerical bounds excess below 0.1 m). Actual coverage remains unverified; valid geometries do not establish complete water mapping.
- `tools/d04_finalize.py` preserves original river lines and generates water-line-visible separately (mapped area difference). It produces gzip GeoJSON, source reports, checksums and licence notices. No browser runtime contract. Finalized N50 staging files under data/prepared/d04/n50 are safe to consider for later D04 implementation; ODbL Herning remains a separate artifact only. GeoDanmark remains the preferred Danish source when access is restored.
- Local finalization completed on all three downloaded artifacts. GitHub preservation workflow reuses exactly those artifacts; it does not reacquire. National source archive downloads total 96,850,418 bytes. Source vintage is not inferred from retrieval date. Actual source coverage, geographical visual review, seam review and D03R runtime integration remain outstanding.
