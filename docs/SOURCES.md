# Source registry

Generated from `web/data/sources.json` (the same list the Almanac shows). Each source's files, URLs, SHA-256 and retrieval dates are in that file and in `data/raw/<id>/manifest.json`.

| id | Title | Publisher | Licence | Used for | Files |
|---|---|---|---|---|---|
| `gisco_grids` | European 1 km grids: EU-DEM elevation, CORINE Land Cover, Tree Cover Density, GEOSTAT population, DEGURBA, service accessibility, road transport performance | Eurostat GISCO / Copernicus Land Monitoring Service / JRC (tiled by J. Gaffuri, github.com/jgaffuri/tiledgrids) | Eurostat/GISCO reuse policy (free reuse with attribution: © EuroGeographics for administrative boundaries; Copernicus data: free, full and open, attribution required) | terrain, land cover, elevation, hex population weights, urban classes, accessibility lenses | 926 |
| `natural_earth` | Natural Earth 1:10m cultural and physical vectors | Natural Earth (naturalearthdata.com), via github.com/nvkelso/natural-earth-vector | Public domain | rivers, lakes, glaciers, roads, railroads, ferries, ports, sea labels, shelf/coast | 18 |
| `boundaries` | Municipal and regional boundaries (Norway 2024, Sweden, Denmark) and NUTS 2024 | Kartverket (NO, via github.com/robhop/fylker-og-kommuner); Valmyndigheten (SE, via github.com/okfse/sweden-geojson); Geodatastyrelsen DAGI (DK, via github.com/Neogeografen/dagi); Eurostat GISCO NUTS 2024 (via github.com/eurostat/Nuts2json) | NO: CC BY 4.0 Kartverket; SE: public data, reuse permitted; DK: free data (Geodatastyrelsen terms); NUTS: © EuroGeographics for the administrative boundaries | municipality of each hex, NUTS 3 region of each municipality, borders | 10 |
| `euronym` | Euronym place-name labels | Eurostat GISCO (from EuroGeographics EuroRegionalMap and the EC towns table) | Eurostat reuse policy; © EuroGeographics | town labels | 3 |
| `ourairports` | OurAirports airport database | OurAirports (David Megginson et al.) | Public domain | airport locations | 1 |
| `powerplants` | powerplantmatching: matched European power plant database | PyPSA / powerplantmatching (Gotzens, Hofmann et al.), combining ENTSO-E, OPSD, JRC, GEO, GPD | Data: CC BY 4.0 (aggregated from open sources; see project for per-source terms) | energy resources on the map (installed capacity, not generation) | 1 |
| `ssb` | Statistics Norway (SSB) StatBank: population, area, employment by place of work, household income | Statistisk sentralbyrå (Statistics Norway) | NLOD 2.0 / CC BY 4.0 (Statistics Norway) | municipal population and growth, age structure, land area, jobs by industry (yields), income lens, university size | 10 |
| `scb` | Statistics Sweden (SCB) Statistical Database: population, land area, employment by place of work, income | Statistiska centralbyrån (Statistics Sweden) | CC0 1.0 (Statistics Sweden open data) | municipal population and growth, age structure, land area, jobs by industry (yields), income lens | 4 |
| `dst` | Statistics Denmark (DST) StatBank: population, area, employment by workplace, income | Danmarks Statistik (Statistics Denmark) | CC BY 4.0 (Statistics Denmark terms of use) | municipal population and growth, age structure, area, jobs by industry (yields), NUTS 3 membership, income lens | 6 |
| `eurostat` | Eurostat: regional GDP (NUTS 3), electricity production, airport passengers, port freight | Eurostat (European Commission) | Eurostat reuse policy (CC BY 4.0) | Gold (GDP), national energy mix, airport size, port size | 5 |
| `regional_accounts` | Regional GDP from the national accounts of Norway, Sweden and Denmark, with Eurostat exchange rates and PPPs | SSB (tables 09391, 11713), SCB (TAB3138), DST (NRHP, INDKP101), Eurostat (ert_bil_eur_a, prc_ppp_ind, nama_10r_3gva) | NLOD/CC BY 4.0 (SSB), CC0 (SCB), CC BY 4.0 (DST, Eurostat) | Gold (GDP) by region, GDP per person lens, apportioned municipal GDP estimate | 9 |
| `wikidata` | Wikidata: World Heritage Sites, universities and national parks in Norway, Sweden and Denmark | Wikidata (Wikimedia Foundation and contributors) | CC0 1.0 | wonders, university locations | 5 |
| `sodir` | Norwegian Offshore Directorate FactPages and FactMaps: oil and gas fields and production | Sokkeldirektoratet (Norwegian Offshore Directorate) | NLOD 2.0 (Norwegian Licence for Open Government Data) | oil and gas resources, petroleum production | 3 |
| `sgu` | SGU Mineral resources database (mines, quarries and deposits) | Sveriges geologiska undersökning (Geological Survey of Sweden) | CC0 1.0 (SGU open data) | mines and mineral deposits | 2 |
| `links` | Fixed links (Wikidata) and main-port freight (Eurostat) | Wikidata contributors; Eurostat | CC0 1.0 (Wikidata); CC BY 4.0 (Eurostat) | engineering wonders, port size | 2 |
| `dsb_shelters` | Tilfluktsrom – Offentlige (public shelters) | Direktoratet for samfunnssikkerhet og beredskap (DSB); WFS hosted by Kartverket (Geonorge) | NLOD 1.0 (Norwegian Licence for Open Government Data) | public shelters layer, municipal shelter summary, Council: civil preparedness notes | 4 |

### Added in v0.2
- `ssb/07459_pop_county2024.json` — SSB 07459 on the 2024 counties (county population series).
- `ssb/klass131_changes_2008_2026.json` — SSB KLASS classification 131 (municipalities), code changes 2008–2026.
- `regional_accounts/ssb_11713_gva_industry.json` — SSB 11713, value added by industry and county, 2023.
- `regional_accounts/nama_10r_3gva.json` — Eurostat nama_10r_3gva, value added by industry, NUTS 3, 2021–2023.
- Derived images `web/data/relief/*` (from CORINE Land Cover 2018, EU-DEM, Copernicus Tree Cover Density, Natural Earth
  bathymetry, Kartverket and DAGI boundaries): produced by `pipeline/build/relief.py`; attribution as for their sources.
- Development-only (not distributed): axe-core (MPL-2.0) for the accessibility journey, Playwright (Apache-2.0).

Attribution: contains data from Statistics Norway, Statistics Sweden, Statistics Denmark, Eurostat (© European Union), Copernicus Land Monitoring Service (EEA), © EuroGeographics for the administrative boundaries, Kartverket, the Norwegian Offshore Directorate, the Geological Survey of Sweden, Natural Earth, OurAirports, Wikidata and powerplantmatching (PyPSA).

### Added in v0.4
- `dsb_shelters/tilfluktsrom_4258.gml` — WFS GetFeature `app:Tilfluktsrom`, EPSG:4258, all 555 features (SHA-256 `97ea06cc…`),
  with `capabilities.xml`, `describe_feature_type.xsd` and `hits.xml` (numberMatched). Retrieved 2026-11-27 through the
  browser relay (same URLs, fetched same-origin from wfs.geonorge.no because the build sandbox refuses the host).
  Attribution: "Contains data under the Norwegian licence for Open Government data (NLOD) made available by DSB."
- Reference only (not redistributed): DSB guidance <https://www.dsb.no/sikkerhverdag/egenberedskap/verdt-a-vite-om-tilfluktsrom/>,
  DSB's official shelter map, data.norge.no dataset page, product specification (Geonorge objektkatalog).
- Investigated, not used: Sweden (Myndigheten för civilt försvar skyddsrumskarta — no openly licensed dataset found),
  Denmark (no published national dataset), Beredskap101's static snapshot (superseded by the official register; see METHODOLOGY).

