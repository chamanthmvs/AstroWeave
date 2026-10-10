"""Account-facing application layer.

Holds the pieces that sit in front of the ``astroweave`` library: SQLite-backed
user/password storage (:mod:`app.auth`) and place-name geocoding
(:mod:`app.geocoding`). Shipped as its own top-level package alongside
``astroweave`` so the FastAPI backend can import it after ``pip install -e .``.
"""
