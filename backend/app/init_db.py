"""Apply versioned migrations, optionally insert missing demo fixtures."""
import argparse

from alembic import command
from alembic.config import Config

from app.config import BACKEND_DIR
from app.database import SessionLocal


def initialize(seed: bool = False) -> None:
    command.upgrade(Config(str(BACKEND_DIR / "alembic.ini")), "head")
    if seed:
        from app.seed import seed_demo

        with SessionLocal.begin() as db:
            seed_demo(db)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", action="store_true", help="Insert missing demo data without replacing existing rows")
    args = parser.parse_args()
    initialize(args.seed)
    print("Database initialized" + ("; demo data ensured" if args.seed else ""))

