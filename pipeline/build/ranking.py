"""One ranking convention for every published rank (NC-R01). web/js/stats.js implements the same rules and is
tested against the same fixture (tests/fixtures/ranking_cases.json).

Comparison population
    The areas being ranked (all municipalities, or a filtered subset such as one country) that have a value.
    Unavailable values (None) are never ranked and never counted in "of N".

Exact rank: competition ("1224") ranking, 1 = largest
    rank_i = 1 + #{j : v_j > v_i}. Equal values share a rank; the next distinct value skips the shared places.
    A list shows tied areas in a deterministic order (name, then id), which does not change their shared rank.

Lower bounds (suppressed cells)
    A value with a suppressed component is published as a lower bound lo_i, with an upper bound hi_i (lo_i plus the
    part of the area's published total that no published component accounts for). For a fully published value
    lo_i = hi_i. The rank shown for the published figures uses lo_i.

Possible-rank interval
    best_i  = 1 + #{j != i : lo_j > hi_i}   (i at its largest possible value, everyone else at their smallest)
    worst_i = 1 + #{j != i : hi_j > lo_i}   (i at its smallest, everyone else at their largest)
    These are exact for the stated bounds: both ends are reached by an assignment of values inside the bounds, and
    the competition rank of the published figures always lies inside them. The bounds themselves are conservative:
    they do not use disclosure thresholds or the national totals that the suppressed cells must add up to, so the
    true range of ranks may be narrower. An interval is published only when best_i != worst_i.
"""
from __future__ import annotations

import math


def _ok(v):
    return v is not None and not (isinstance(v, float) and math.isnan(v))


def competition(vals):
    """Competition ranks (1 = largest) for a list of values; None for unavailable values."""
    present = sorted((v for v in vals if _ok(v)), reverse=True)
    first = {}
    for pos, v in enumerate(present, 1):
        first.setdefault(v, pos)
    return [first[v] if _ok(v) else None for v in vals]


def intervals(lo, hi):
    """Possible-rank interval [best, worst] for each area given lower and upper bounds; None if unavailable."""
    idx = [i for i, v in enumerate(lo) if _ok(v)]
    out = [None] * len(lo)
    for i in idx:
        h = hi[i] if _ok(hi[i]) else lo[i]
        best = 1 + sum(1 for j in idx if j != i and lo[j] > h)
        worst = 1 + sum(1 for j in idx if j != i and (hi[j] if _ok(hi[j]) else lo[j]) > lo[i])
        out[i] = [best, worst]
    return out


def order(vals, names, ids):
    """Deterministic display order: value descending, then name, then id; unavailable values left out."""
    return sorted((i for i, v in enumerate(vals) if _ok(v)), key=lambda i: (-vals[i], str(names[i]), str(ids[i])))


def apply(objs, key, vals, his=None):
    """Write ranks[key] (and rank_range[key] where uncertain) onto each object, returning the comparison size."""
    ranks = competition(vals)
    for o, r in zip(objs, ranks):
        o.setdefault("ranks", {})[key] = r
        (o.get("rank_range") or {}).pop(key, None)
    if his is not None and any(_ok(h) and _ok(v) and h > v for v, h in zip(vals, his)):
        for o, iv in zip(objs, intervals(vals, his)):
            if iv and iv[0] != iv[1]:
                o.setdefault("rank_range", {})[key] = iv
    for o in objs:
        if "rank_range" in o and not o["rank_range"]:
            del o["rank_range"]
    return sum(1 for v in vals if _ok(v))
