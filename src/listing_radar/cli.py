"""listing-radar — demand research for Etsy sellers, from public data."""
from __future__ import annotations

import argparse
import sys

from . import config
from .client import EtsyClient, QuotaExhausted
from .commands import demand, rank, traction


def traction_target(value: str) -> tuple[str, int]:
    """argparse type for traction's target: a bare listing id (e.g. 12345) or
    shop:<shop_id> (e.g. shop:678). Returns ("listing"|"shop", id).

    Doing the int() conversion here — instead of inside main()'s try block —
    means a typo'd id fails the same clean way --sample's type=int already
    does: argparse rejects it and exits before main() ever runs, instead of
    an uncaught ValueError escaping as a raw traceback.
    """
    kind, raw_id = ("shop", value[5:]) if value.startswith("shop:") else ("listing", value)
    try:
        return kind, int(raw_id)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"{value!r} is not a valid traction target "
            f"(expected a listing id, e.g. 12345, or shop:<shop_id>, e.g. shop:12345)"
        ) from None


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
    t.add_argument("target", type=traction_target, help="a listing id, or shop:<shop_id>")

    r = sub.add_parser("rank", help="why a listing gets no views")
    r.add_argument("phrase")
    r.add_argument("--listing", type=int, required=True, dest="listing_id")
    r.add_argument("--depth", type=int, default=rank.DEPTH,
                   help="how deep to look before calling it absent")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        client = EtsyClient()
        if args.command == "demand":
            print(demand.render(demand.analyse(client, args.phrase, args.sample)))
        elif args.command == "traction":
            kind, target_id = args.target
            if kind == "shop":
                result = traction.for_shop(client, target_id)
            else:
                result = traction.for_listing(client, target_id)
            print(traction.render(result))
        elif args.command == "rank":
            print(rank.render(rank.probe(client, args.phrase,
                                         args.listing_id, args.depth)))
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
