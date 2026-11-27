"""Builders: interim data -> web/data/*.json, in dependency order."""
BUILDERS = []


def run(names):
    import importlib
    order = ["world", "regions", "munis", "relief", "resources", "infrastructure", "wonders", "shelters", "uplinks", "lenses", "catalog"]
    for name in order:
        if names and name not in names:
            continue
        try:
            mod = importlib.import_module(f"pipeline.build.{name}")
        except ModuleNotFoundError as e:
            if e.name == f"pipeline.build.{name}":
                print(f"build {name}: (not implemented)")
                continue
            raise
        import time
        t0 = time.time()
        mod.build()
        print(f"build {name:14s} ok ({time.time()-t0:.1f}s)")
