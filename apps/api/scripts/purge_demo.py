"""Delete every demo-flagged project (development/demo data only).

Never touches real projects. Every deletion is written to the audit log.

Run from ``apps/api``:

    python -m scripts.purge_demo --yes
"""

from __future__ import annotations

import argparse
import sys

from app.core.logging import setup_logging
from app.db.session import SessionLocal
from app.services.audit import Actor
from app.services.projects import purge_demo_projects


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Required confirmation flag; without it nothing is deleted.",
    )
    args = parser.parse_args(argv)
    setup_logging()
    if not args.yes:
        print("Refusing to delete without --yes.")
        return 2
    actor = Actor(type="system", label="پاک سازی داده نمایشی")
    with SessionLocal() as db:
        result = purge_demo_projects(db, actor=actor)
        db.commit()
    print(f"Deleted {result['deleted']} demo project(s).")
    for item in result["projects"]:
        print(f"  - {item['name']} ({item['id']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
