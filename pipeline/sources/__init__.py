"""Source registry: every Source subclass listed here is fetched/processed by the CLI."""
from .climate import ClimateNormals
from .commuting import Commuting
from .nordic_commuting import NordicCommuting
from .nve_environment import NveEnvironment
from .transport import Transport
from .geo import Boundaries, Euronym, GiscoGrids, NaturalEarth, OurAirports, PowerPlants
from .stats import DST_, SCB_, SSB_, Eurostat

ALL = [GiscoGrids(), NaturalEarth(), Boundaries(), Euronym(), OurAirports(), PowerPlants(),
       SSB_(), SCB_(), DST_(), Eurostat(), ClimateNormals(), NveEnvironment(), Commuting(), NordicCommuting("SE"), NordicCommuting("DK"), Transport()]


def _extra_sources():
    """Sources defined in other modules (resources, wonders, shelters, camera uplinks); imported lazily to keep import errors local."""
    out = []
    try:
        from .extra import RESOURCE_SOURCES
        out += RESOURCE_SOURCES
    except ImportError:
        pass
    try:
        from .shelters import Shelters
        out.append(Shelters())
    except ImportError:
        pass
    try:
        from .uplinks import CameraUplinks
        out.append(CameraUplinks())
    except ImportError:
        pass
    return out


def registry() -> dict:
    return {s.id: s for s in ALL + _extra_sources()}
