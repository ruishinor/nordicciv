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


def coordinate(value: str) -> float:
    parts = value.strip().split("|")
    if len(parts) != 4 or parts[3] not in {"N", "S", "E", "W"}:
        raise ValueError(f"Invalid WMO coordinate: {value!r}")
    deg, minute, second = map(float, parts[:3])
    if not (math.isfinite(deg) and 0 <= deg <= 180 and 0 <= minute < 60 and 0 <= second < 60):
        raise ValueError("Invalid WMO coordinate range")
    return round((deg + minute / 60 + second / 3600) * (-1 if parts[3] in "SW" else 1), 6)


def number(value: str) -> float | None:
    value = value.strip()
    if value in {"", "NA", "N/A", "-", "...", "-9999", "-999.9"}:
        return None
    n = float(value)
    if not math.isfinite(n):
        raise ValueError("Non-finite climate normal")
    return n


def parse_station(raw: bytes, country: str, url: str) -> dict:
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("cp1252")  # Danish archive files contain Ø/Æ in Windows-1252.
    rows = [[v.strip() for v in r] for r in csv.reader(io.StringIO(text))]
    if "1991-2020" not in rows[0][0]:
        raise ValueError("Unexpected climate reference period")
    names, coords, values, counts, units = {}, None, {}, {}, {}
    for i, r in enumerate(rows):
        if not r:
            continue
        if r[0] in {"Country_Name", "Station_Name"}:
            names[r[0]] = r[1]
        if len(r) > 3 and r[:3] == ["WMO_Number", "Latitude", "Longitude"]:
            coords = rows[i + 1]
        if r[0] == "Parameter_Code" and i + 1 < len(rows):
            p = rows[i + 1]
            if p and p[0] in {"1", "5"}:
                units[p[0]] = p[2].lower()
        if len(r) < 17 or r[1] not in {"1", "5"}:
            continue
        expected = ("sum", "4") if r[1] == "1" else ("mean", "1")
        if (r[2].lower(), r[3]) == expected:
            if r[1] in values:
                raise ValueError("Duplicate climate parameter")
            values[r[1]] = [number(v) for v in r[4:17]]
        elif r[2].upper() == "NOY" and r[3] == "98":
            if r[1] in counts:
                raise ValueError("Duplicate year counts")
            counts[r[1]] = [number(v) for v in r[4:17]]
    if not coords or names.get("Country_Name", "").lower() != SELECTION[country][0].lower():
        raise ValueError("Missing or mismatched station identity")
    lat, lon = coordinate(coords[1]), coordinate(coords[2])
    if not (54 <= lat <= 72 and 3 <= lon <= 32):
        raise ValueError("Station outside mainland Scandinavia")
    for p, expected in {"1": "mm", "5": "deg_c"}.items():
        if p in values and units.get(p) != expected:
            raise ValueError(f"Unexpected units for parameter {p}")
        for i, n in enumerate(values.get(p, [None] * 13)):
            if n is not None and not ((0 <= n <= 7000) if p == "1" else (-65 <= n <= 45)):
                raise ValueError("Climate value outside physical bounds")
            count = counts.get(p, [None] * 13)[i]
            if count is not None and not 0 <= count <= 30:
                raise ValueError("Invalid number of years")
            if count is not None and count < 24:
                values[p][i] = None
    station = {
        "id": f"{country}-{coords[0].zfill(5)}", "country": country,
        "name": names["Station_Name"].replace("_", " ").title(),
        "lat": lat, "lon": lon, "elevation_m": number(coords[3]),
        "temperature_c": values.get("5", [None] * 13)[:12],
        "precipitation_mm": values.get("1", [None] * 13)[:12],
        "annual_temperature_c": values.get("5", [None] * 13)[12],
        "annual_precipitation_mm": values.get("1", [None] * 13)[12],
        "temperature_years": counts.get("5", [None] * 13),
        "precipitation_years": counts.get("1", [None] * 13),
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
        license="CC0 1.0 (NCEI accession 0253808 metadata); national agency attribution retained",
        description="Selected station monthly and annual temperature and precipitation normals, 1991–2020. "
                    "National meteorological agency submissions in NCEI archive version 6.6; not municipal averages.",
        used_for=["Nearby station climate profiles", "Climate station exploration"],
    )

    def files(self):
        return [File(f"{cc}/{name}.csv", f"{BASE}{folder}/CSV/{name}.csv")
                for cc, (folder, names) in SELECTION.items() for name in names]

    def process(self):
        stations = []
        for f in self.files():
            ok, reason = fetch.verify(self.id, f.rel_path, url=f.url)
            if not ok:
                raise ValueError(f"Climate cache {f.rel_path}: {reason}")
            stations.append(parse_station(self.path(f.rel_path).read_bytes(), f.rel_path[:2], f.url))
        ids = [s["id"] for s in stations]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate climate station ids")
        return {"period": PERIOD, "archive_version": "6.6", "stations": stations,
                "source": self.info.to_dict(), "manifest": fetch.read_manifest(self.id)}
