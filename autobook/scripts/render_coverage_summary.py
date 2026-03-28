from __future__ import annotations

import argparse
import xml.etree.ElementTree as ET
from pathlib import Path


def percentage(value: float) -> str:
    return f"{value * 100:.2f}%"


def build_summary(xml_path: Path) -> str:
    root = ET.parse(xml_path).getroot()
    total_line_rate = float(root.attrib["line-rate"])
    total_branch_rate = float(root.attrib.get("branch-rate", 0.0))

    lines = [
        "## Coverage Summary",
        "",
        f"- Line coverage: **{percentage(total_line_rate)}**",
        f"- Branch coverage: **{percentage(total_branch_rate)}**",
        "",
        "| Package | Line Coverage |",
        "| --- | ---: |",
    ]

    for package in root.findall(".//package"):
        lines.append(
            f"| `{package.attrib['name']}` | {percentage(float(package.attrib['line-rate']))} |"
        )

    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--xml", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    summary = build_summary(args.xml)
    if args.output:
        args.output.write_text(summary, encoding="utf-8")
    else:
        print(summary)


if __name__ == "__main__":
    main()
