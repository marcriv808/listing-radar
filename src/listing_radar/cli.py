"""listing-radar — demand research for Etsy sellers, from public data."""
from __future__ import annotations

import argparse
import sys

from . import config
from .client import EtsyClient, QuotaExhausted
from .commands import demand, traction


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="listing-radar",
        description="Demand research for Etsy sellers, from public listing data. "
                    "Read-only: this tool never writes to a shop.",
    )
    sub = p.add_subparsers(dest="command", required=True)

    d = sub.add_parser("demand", help="is anyone searching for this phrase")
    d.add_argument("phrase")
    d.add_argument("--sample", type=int, default=100,
                   help="how many ranked listings to sample (max 100)")

    t = sub.add_parser("traction", help="how well is a competitor doing")
    t.add_argument("target", help="a listing id, or shop:<shop_id>")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        client = EtsyClient()
        if args.command == "demand":
            print(demand.render(demand.analyse(client, args.phrase, args.sample)))
        elif args.command == "traction":
            if args.target.startswith("shop:"):
                result = traction.for_shop(client, int(args.target[5:]))
            else:
                result = traction.for_listing(client, int(args.target))
            print(traction.render(result))
    except config.MissingCredentials as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    except QuotaExhausted as e:
        print(f"error: {e}", file=sys.stderr)
        return 3
    except RuntimeError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
