"""Compatibility wrapper for the Japan-first seed path.

Historically this script seeded a few Chicago sample properties. The product is
now Japan-first, so the default sample inventory comes from the Tokyo fixture
corpus instead.
"""

from scripts.seed_tokyo import main


if __name__ == "__main__":
    main()
