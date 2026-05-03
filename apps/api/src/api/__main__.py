"""Allow `python -m api`."""

import sys

from api.cli import main

if __name__ == "__main__":
    sys.exit(main())
