"""Publish the validated Norwegian commuting matrix selection."""
import argparse
from ..core.paths import WEB_DATA
from ..core.store import write_json
from ..sources.commuting import Commuting
from .catalog import update_source


def build(write=True):
    source = Commuting()
    packet = source.process()
    print(f"Commuting: {len(packet['flows'])} directed published pairs; {packet['audit']}", flush=True)
    if write:
        write_json(WEB_DATA / "commuting.json", packet)
        update_source(source)
    return packet


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--fetch",action="store_true")
    if p.parse_args().fetch:
        queued = Commuting().fetch()
        if queued:
            raise RuntimeError(f"Commuting source requests not acquired: {queued}")
    build()
