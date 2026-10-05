#!/usr/bin/env python3
"""Compatibility view of the single lifecycle workflow; prefer run.py."""
import json
from run import run as lifecycle


def run():
    return lifecycle()["named"]


if __name__ == "__main__":
    print(json.dumps(run(), sort_keys=True))
