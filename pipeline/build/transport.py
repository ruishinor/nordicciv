"""Build only the observed transport selection."""
import argparse
from ..sources.transport import Transport
from ..core.paths import WEB_DATA
from ..core.store import write_json
from .catalog import update_source


def build(write=True):
    source = Transport()
    packet = source.process()
    if write:
        write_json(WEB_DATA / "transport.json", packet)
        update_source(source)
    return packet


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--fetch", action="store_true")
    if p.parse_args().fetch and Transport().fetch():
        raise RuntimeError("Transport sources not acquired")
    print(f"Published {len(build()['flows'])} transport observations")
