# PowerCenter XML parser

This package reads PowerCenter repository exports into a small Python object model. It uses only Python's standard library and does not contain mapping-specific or Jaffle Shop-specific logic.

```python
from pwc_parser import parse_file

document = parse_file("FLOWLINE_DEMO_JAFFLESHOP.xml")
for mapping in document.iter_mappings():
    print(mapping.name)
    for transform in mapping.iter_transformations():
        print(transform.name, transform.attributes.get("TYPE"))
    for edge in mapping.iter_connections_from("SQ_RAW_CUSTOMERS"):
        print(edge.from_field, "->", edge.to_instance, edge.to_field)
```

Run an inventory from the repository root with:

```sh
PYTHONPATH=src python -m pwc_parser FLOWLINE_DEMO_JAFFLESHOP.xml
```

`Definition.attributes` and `Field.attributes` preserve XML attributes (normalized to uppercase keys), including properties that a later converter may not yet understand. Mapping instances are separate from transformation definitions because one definition can be instantiated more than once.
