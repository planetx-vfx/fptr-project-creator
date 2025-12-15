"""Main start file for the NFA ShotGrid Project Creator, written by Mervin van Brakel (2024)"""

import argparse
import sys

from PySide2 import QtWidgets

from controller import ProjectCreatorController


def parse_args():
    parser = argparse.ArgumentParser(
        description="Command-line interface for opening project creator."
    )

    # Required arguments
    parser.add_argument("--sg-url", required=True, help="Url to the FPTR site.")
    parser.add_argument("--script-name", required=True, help="Name of the API script.")
    parser.add_argument("--api-key", required=True, help="The API key.")

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    app = QtWidgets.QApplication(sys.argv)

    controller = ProjectCreatorController(args.sg_url, args.script_name, args.api_key)

    sys.exit(app.exec_())
