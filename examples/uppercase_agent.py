"""A tiny agent used only to demonstrate the runner's stdin/stdout protocol."""

import sys


def main() -> None:
    sys.stdout.write(sys.stdin.read().strip().upper())


if __name__ == "__main__":
    main()

