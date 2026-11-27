"""Source registry: every Source subclass listed here is fetched/processed by the CLI."""
from .geo import Boundaries, Euronym, GiscoGrids, NaturalEarth, OurAirports, PowerPlants
from .stats import DST_, SCB_, SSB_, Eurostat

ALL = [GiscoGrids(), NaturalEarth(), Boundaries(), Euronym(), OurAirports(), PowerPlants(),
       SSB_(), SCB_(), DST_(), Eurostat()]


def extra():
    """Sources defined in other modules (resources, wonders); imported lazily to keep import errors local."""
    out = []
    try:
        from .extra import RESOURCE_SOURCES
        out += RESOURCE_SOURCES
    except ImportError:
        pass
    return out


def registry() -> dict:
    return {s.id: s for s in ALL + extra()}
