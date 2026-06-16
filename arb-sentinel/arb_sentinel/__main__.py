import argparse, sys
from .config import load_settings
from . import run as run_mod


def main(argv=None):
    p = argparse.ArgumentParser(prog="arb_sentinel")
    p.add_argument("--task", required=True,
                   choices=["rates", "digest", "test", "announcements", "depeg", "exits", "monitor"])
    args = p.parse_args(argv)
    cfg = load_settings()
    dispatch = {"rates": run_mod.run_rates, "digest": run_mod.run_digest,
                "announcements": run_mod.run_announcements,
                "test": lambda c: run_mod.run_test(c),
                "depeg": run_mod.run_depeg, "exits": run_mod.run_exits,
                "monitor": run_mod.run_monitor}
    fn = dispatch.get(args.task)
    if fn is None:
        print(f"[run] task '{args.task}' not implemented yet (later milestone)", file=sys.stderr)
        return 0
    n = fn(cfg)
    print(f"[run] task={args.task} notifications={n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
