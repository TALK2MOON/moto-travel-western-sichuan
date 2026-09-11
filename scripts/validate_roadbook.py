#!/usr/bin/env python3
"""Validate a roadbook JSON before export."""

import argparse
import json
import sys

from roadbook_utils import validate_roadbook


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("roadbook", help="路书 JSON 文件")
    args = parser.parse_args()
    try:
        with open(args.roadbook, encoding="utf-8") as handle:
            roadbook = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        sys.exit(f"无法读取路书: {exc}")
    errors = validate_roadbook(roadbook)
    if errors:
        sys.exit("路书校验失败:\n- " + "\n- ".join(errors))
    print(f"校验通过: {len(roadbook['days'])} 天, 坐标系 {roadbook['coordinate_system']}")


if __name__ == "__main__":
    main()
