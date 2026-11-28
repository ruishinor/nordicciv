"""Bounded Scandinavian WMO 1991–2020 station normals, archived by NOAA NCEI.

Only WMO parameters 1 (precipitation total, mm) and 5 (daily mean temperature,
degrees C) are selected. These are national meteorological agency submissions,
not NOAA model estimates. Missing observations remain missing. Published NOY
counts below 24 years are withheld; an omitted NOY is explicitly unknown.
"""
from __future__ import annotations

import csv
import io
import math
from ..core.source import File, Source, SourceInfo
from ..core import fetch

BASE = "https://www.ncei.noaa.gov/data/oceans/archive/arc0216/0253808/6.6/data/0-data/Region-6-WMO-Normals-9120/"
PERIOD = [1991, 2020]
MONTHS = "January February March April May June July August September October November December Annual".split()
MIN_YEARS = 24
PUBLISHERS = {"NO": "MET Norway", "SE": "SMHI", "DK": "DMI"}
LICENSE_URL = "https://catalog.data.gov/dataset/wmo-climatological-standard-normals-for-1991-2020-ncei-accession-0253808"
# Deliberate geographical sample: coast/inland, north/south, mountains and cities.
# Exact archive filenames, verified against the official 6.6 directory listing.
SELECTION = {
    "NO": ("Norway", ["BERGEN_FLORIDA_01317", "OSLO_BLINDERN_01492", "TROMSO_01026",
        "TRONDHEIM_VOLL_01257", "BODO_VI_01152", "KAUTOKEINO_01047", "KARASJOK_MARKANNJARGA_01065",
        "KIRKENES_LUFTHAVN_01089", "SLETTNES_FYR_01078", "SOLA_01415", "KJEVIK_01452",
        "LAERDAL_IV_01355", "ROROS_LUFTHAVN_01288", "FOKSTUGU_01238", "GEILO_01359",
        "TAFJORD_01218", "FINSEVATN_01350", "VOSSEVANGEN_01337"]),
    "SE": ("Sweden", ["Stockholm_Observatoriekullen_02485", "Stockholm_Observatoriekullen_A_02484",
        "Goteborg_A_02513", "Malmo_A_02635", "Lund_02631", "Kiruna_Flygplats_02044",
        "Abisko_Aut_02022", "Karesuando_A_02081", "Lulea_Kallax_Flygplats_02186",
        "Umea_Flygplats_02286", "Ostersund_Froson_Flygplats_02226", "Sundsvall_Timra_Flygplats_02366",
        "Borlange_Flygplats_02435", "Karlstad_Flygplats_02418", "Visby_Flygplats_02590",
        "Vaxjo_A_02648", "Norrkoping_SMHI_02574", "Tarfala_A_02029"]),
    "DK": ("Denmark", ["BILLUND_LUFTHAVN_06104", "H_C_ANDERSEN_AIRPORT_06120",
        "LANDBOHYJSKOLEN_06186", "ROSKILDE_LUFTHAVN_06170", "SJAELSMARK_06188",
        "SKAGEN_FYR_06041", "ODUM_06072", "NORDBY_06088", "HAMMER_ODDE_FYR_06193",
        "SILSTRUP_06019", "STORE_JYNDEVAD_06116", "TYLSTRUP_06031"]),
}


def coordinate(value: str, hemispheres: str) -> float:
    parts = value.strip().split("|")
    if len(parts) != 4 or parts[3] not in tuple(hemispheres):
        raise ValueError(f"Invalid WMO coordinate: {value!r}")
    deg, minute, second = map(float, parts[:3])
    limit = 90 if hemispheres == "NS" else 180
    if not (0 <= deg <= limit and 0 <= minute < 60 and 0 <= second < 60
            and deg + minute / 60 + second / 3600 <= limit):
        raise ValueError("Invalid WMO coordinate range")
    return round((deg + minute / 60 + second / 3600) * (-1 if parts[3] in "SW" else 1), 6)


def number(value: str) -> float | None:
    value = value.strip()
    if value.upper() in {"", "NA", "N/A", "-", "..."}:
        return None
    n = float(value)
    if n in {-9999, -999.9}:
        return None
    if not math.isfinite(n):
        raise ValueError("Non-finite climate normal")
    return n


def parse_station(raw: bytes, country: str, url: str) -> dict:
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("cp1252")  # Danish archive files contain Ø/Æ in Windows-1252.
    rows = [[v.strip() for v in r] for r in csv.reader(io.StringIO(text))]
    if not rows or not rows[0] or "1991-2020" not in rows[0][0]:
        raise ValueError("Unexpected climate reference period")
    names, coords, values, counts, units = {}, None, {}, {}, {}
    month_order_valid = False
    for i, r in enumerate(rows):
        if not r:
            continue
        if len(r) >= 2 and r[0] in {"Country_Name", "Station_Name"}:
            names[r[0]] = r[1]
        if len(r) > 3 and r[:3] == ["WMO_Number", "Latitude", "Longitude"]:
            coords = rows[i + 1]
        if r[0] == "Parameter_Code" and i + 1 < len(rows):
            month_order_valid = False
            p = rows[i + 1]
            if len(p) >= 3 and p[0] in {"1", "5"}:
                units[p[0]] = p[2].lower()
        if r[:4] == ["WMO_Number", "Parameter_Code", "Calculation_Name", "Calculation_Code"]:
            month_order_valid = r[4:17] == MONTHS
        if len(r) < 4 or not r[0].isdigit() or r[1] not in {"1", "5"}:
            continue
        expected = ("sum", "4") if r[1] == "1" else ("mean", "1")
        calculation = (r[2].lower(), r[3])
        if calculation not in {expected, ("noy", "98")}:
            continue
        if not month_order_valid or not coords or r[0].zfill(5) != coords[0].zfill(5) or len(r) < 17:
            raise ValueError("Invalid climate data row")
        table = counts if calculation == ("noy", "98") else values
        if r[1] in table:
            raise ValueError("Duplicate climate data row")
        table[r[1]] = [number(v) for v in r[4:17]]
    if (not coords or len(coords) < 4 or not coords[0].isdigit() or not names.get("Station_Name")
            or names.get("Country_Name", "").lower() != SELECTION[country][0].lower()):
        raise ValueError("Missing or mismatched station identity")
    lat, lon = coordinate(coords[1], "NS"), coordinate(coords[2], "EW")
    if not (54 <= lat <= 72 and 3 <= lon <= 32):
        raise ValueError("Station outside mainland Scandinavia")
    for p, expected in {"1": "mm", "5": "deg_c"}.items():
        if p in values and units.get(p) != expected:
            raise ValueError(f"Unexpected units for parameter {p}")
        values.setdefault(p, [None] * 13)
        counts.setdefault(p, [None] * 13)
        for i, n in enumerate(values[p]):
            if n is not None and not ((0 <= n <= 7000) if p == "1" else (-65 <= n <= 45)):
                raise ValueError("Climate value outside physical bounds")
            count = counts[p][i]
            if count is not None:
                if not (count.is_integer() and 0 <= count <= 30):
                    raise ValueError("Invalid number of years")
                counts[p][i] = int(count)
                if count < MIN_YEARS:
                    values[p][i] = None
    archive_name = names["Station_Name"].replace("_", " ").title()
    # The Norwegian submission uses ASCII. Restore local spelling in the map label.
    display_names = {"01026": "Tromsø", "01152": "Bodø VI", "01355": "Lærdal IV", "01288": "Røros lufthavn"}
    wmo_id = coords[0].zfill(5)
    station = {
        "id": f"{country}-{wmo_id}", "country": country,
        "name": display_names.get(wmo_id, archive_name) if country == "NO" else archive_name,
        "lat": lat, "lon": lon, "elevation_m": number(coords[3]),
        "temperature_c": values["5"][:12],
        "precipitation_mm": values["1"][:12],
        "annual_temperature_c": values["5"][12],
        "annual_precipitation_mm": values["1"][12],
        "temperature_years": counts["5"],
        "precipitation_years": counts["1"],
        "source_url": url,
    }
    if not any(n is not None for p in ("temperature_c", "precipitation_mm") for n in station[p]):
        raise ValueError("Station has no eligible temperature or precipitation normals")
    return station


class ClimateNormals(Source):
    info = SourceInfo(
        id="climate_normals", title="WMO station climate normals, 1991–2020",
        publisher="MET Norway, SMHI and DMI; WMO / NOAA NCEI archive",
        homepage="https://www.ncei.noaa.gov/products/wmo-climate-normals",
        license="CC0 1.0 (NOAA NCEI accession 0253808)",
        description="Selected station monthly and annual temperature and precipitation normals, 1991–2020. "
                    "National meteorological agency submissions in NCEI archive version 6.6; not municipal averages.",
        used_for=["Nearby station climate profiles", "Climate station exploration"],
    )

    def files(self):
        return [File(f"{cc}/{name}.csv", f"{BASE}{folder}/CSV/{name}.csv")
                for cc, (folder, names) in SELECTION.items() for name in names]

    def process(self):
        stations = []
        manifest = fetch.read_manifest(self.id)
        for f in self.files():
            path = self.path(f.rel_path)
            ok, reason = fetch.verify(self.id, f.rel_path, url=f.url)
            if not ok:
                raise ValueError(f"Climate cache {f.rel_path}: {reason}")
            try:
                station = parse_station(path.read_bytes(), f.rel_path[:2], f.url)
                if station["id"] != f"{f.rel_path[:2]}-{path.stem.rsplit('_', 1)[1]}":
                    raise ValueError("Station ID differs from the archive filename")
            except ValueError as exc:
                raise ValueError(f"Climate cache {f.rel_path}: {exc}") from exc
            entry = manifest["files"][f.rel_path]
            stations.append({**station, "sha256": entry["sha256"], "retrieved": entry["retrieved"]})
        ids = [s["id"] for s in stations]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate climate station ids")
        return {"period": PERIOD, "archive_version": "6.6", "stations": stations,
                "minimum_years": MIN_YEARS, "publishers": PUBLISHERS, "license_url": LICENSE_URL,
                "source": self.info.to_dict()}
