"""Map projection and vectorised hex lookup.

The map uses a Lambert azimuthal equal-area projection centred on Scandinavia (63°N, 15°E, GRS80), in km.
Equal-area keeps hex statistics honest (every hex covers the same ground area); centring on 63°N/15°E keeps
shape distortion small from Jutland to the North Cape (the standard European LAEA, EPSG:3035, is centred on
52°N/10°E and visibly shears northern Norway). Map coordinates are km with y pointing down (as in usaciv).
"""
from __future__ import annotations

import math

import numpy as np
from pyproj import Transformer

NORDIC_LAEA = "+proj=laea +lat_0=63 +lon_0=15 +x_0=0 +y_0=0 +ellps=GRS80 +units=km +no_defs"

_from_ll = Transformer.from_crs("EPSG:4326", NORDIC_LAEA, always_xy=True)
_to_ll = Transformer.from_crs(NORDIC_LAEA, "EPSG:4326", always_xy=True)
_from_3035 = Transformer.from_crs("EPSG:3035", NORDIC_LAEA, always_xy=True)
_3035_to_ll = Transformer.from_crs("EPSG:3035", "EPSG:4326", always_xy=True)

SQRT3 = math.sqrt(3)


class Frame:
    """Map frame: projected km -> map km (origin top-left, y down)."""

    def __init__(self, x0: float, y1: float):
        self.x0, self.y1 = x0, y1  # projected west edge and north edge

    def from_ll(self, lon, lat):
        x, y = _from_ll.transform(np.asarray(lon, dtype=float), np.asarray(lat, dtype=float))
        return x - self.x0, self.y1 - y

    def from_3035(self, X, Y):
        x, y = _from_3035.transform(np.asarray(X, dtype=float) / 1.0, np.asarray(Y, dtype=float))
        return x - self.x0, self.y1 - y

    def to_ll(self, mx, my):
        lon, lat = _to_ll.transform(np.asarray(mx, dtype=float) + self.x0, self.y1 - np.asarray(my, dtype=float))
        return lon, lat

    def to_dict(self):
        return {"proj4": NORDIC_LAEA, "x0_km": self.x0, "y1_km": self.y1,
                "note": "map x = projected x - x0_km; map y = y1_km - projected y (km, y down)"}


def ll_from_3035(X, Y):
    return _3035_to_ll.transform(np.asarray(X, dtype=float), np.asarray(Y, dtype=float))


def projected_from_ll(lon, lat):
    return _from_ll.transform(np.asarray(lon, dtype=float), np.asarray(lat, dtype=float))


def cell_at(x, y, radius: float, cols: int, rows: int):
    """Vectorised HexGrid.cell_at (pointy-top, odd-r): returns cell indices, -1 outside the grid."""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    q = (SQRT3 / 3 * x - y / 3) / radius
    r = (2 / 3 * y) / radius
    cx, cz = q, r
    cy = -cx - cz
    rx, ry, rz = np.floor(cx + 0.5), np.floor(cy + 0.5), np.floor(cz + 0.5)
    dx, dy, dz = np.abs(rx - cx), np.abs(ry - cy), np.abs(rz - cz)
    a = (dx > dy) & (dx > dz)
    b = ~a & (dy <= dz)
    rx = np.where(a, -ry - rz, rx)
    rz = np.where(b, -rx - ry, rz)
    row = rz.astype(np.int64)
    col = (rx + (row - (row & 1)) // 2).astype(np.int64)
    ok = (col >= 0) & (row >= 0) & (col < cols) & (row < rows)
    return np.where(ok, row * cols + col, -1)


def centers(radius: float, cols: int, rows: int):
    idx = np.arange(cols * rows)
    col, row = idx % cols, idx // cols
    return SQRT3 * radius * (col + 0.5 * (row & 1)), 1.5 * radius * row
