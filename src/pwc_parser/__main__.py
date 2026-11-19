"""Print a compact inventory for a PowerCenter XML file."""

import argparse
import json

from .parser import parse_file


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("xml_file", help="PowerCenter repository XML export")
    args = parser.parse_args()
    document = parse_file(args.xml_file)
    print(json.dumps({
        "repositories": [item.name for item in document.repositories],
        "folders": [item.name for item in document.folders],
        "sources": [item.name for item in document.sources],
        "targets": [item.name for item in document.targets],
        "mappings": [{
            "name": mapping.name,
            "transformations": [t.name for t in mapping.transformations],
            "instances": len(mapping.instances),
            "connections": len(mapping.connections),
        } for mapping in document.mappings],
    }, indent=2))


if __name__ == "__main__":
    main()
