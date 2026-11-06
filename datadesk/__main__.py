"""Allow launching DataDesk with ``python -m datadesk``."""

from datadesk.app import main


if __name__ == "__main__":
    raise SystemExit(main())
