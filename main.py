from maplebot.cli import run_cli
from maplebot.gui import run_gui


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="MapleBot controller")
    parser.add_argument("--cli", action="store_true", help="Run in keyboard-listener CLI mode.")
    args = parser.parse_args()

    if args.cli:
        run_cli()
    else:
        run_gui()


if __name__ == "__main__":
    main()
