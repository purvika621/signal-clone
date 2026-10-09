"""Production entry point: additive migrations, then exactly one ASGI worker."""
import uvicorn

from app.config import settings
from app.init_db import initialize


def main():
    initialize()  # Never resets data or automatically seeds accounts.
    uvicorn.run("app.main:app", host="0.0.0.0", port=settings.port, workers=1)


if __name__ == "__main__":
    main()
