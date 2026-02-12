"""python -m chessdna entrypoint.

This makes it easy to run the CLI without relying on an installed console script.
"""

from .cli import main


if __name__ == "__main__":
    main()
