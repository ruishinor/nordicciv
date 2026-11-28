"""Targeted Nordic commuting acquisition. Never rewrites Norway or unrelated datasets."""
import argparse
from ..core.paths import WEB_DATA
from ..core.store import write_json
from ..sources.nordic_commuting import NordicCommuting
from .catalog import update_source

def build(acquire=False):
    sources=[NordicCommuting(country) for country in ("SE","DK")]
    packets=[]
    for s in sources:
        if acquire and s.fetch():
            raise RuntimeError(f"Source not acquired: {s.id}")
        packet=s.process()
        packets.append(packet)
        print(f"{s.id}: {len(packet['flows'])} qualifying pairs; {packet['audit']}",flush=True)
    # Only publish after both independently validated packets are ready.
    for s,packet in zip(sources,packets):
        write_json(WEB_DATA/(s.id+".json"),packet)
        update_source(s)
    return packets

if __name__ == "__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--fetch",action="store_true")
    build(p.parse_args().fetch)
