# How to install

Dockerfile creates an isolated environment for development and tests.
It has python 3.14, pytest, dbt, duckdb (used as a playground to experient and test with dbt, seeds, data, etc).
It's not intended as a production grade container only as an isolated safe environment for developers who won't need to make custom setups on their system.
Just build the docker image, and run the container. Then attach to it and test. All dependencies are there ready set up.

Build docker with:
```bash
cd docker

# for development and debugging
# build the docker image with python, pytest (and other pips), dbt, duckdb and related stuff used for running tests and playground with data
docker build -t infinite-lambda-dbt .

# create the container (map local directory of your project to /workspace inside the container)
docker create \
    -it \
    --name mytest \
    -v "/local/path/on/your/computer:/workspace" \
    infinite-lambda-dbt

# start container if not running
docker start infinite-lambda-dbt

# attach to run commands, tests, and experiment
docker attach infinite-lambda-dbt
```

# Run tests

```bash
PYTHONPATH=src python -m pytest -q
```

# Command-line tool

This is the tool that can be used to run different parts of the process and check results.
It can be used to produce the final generation of dbt models as well.

The manual CLI is available at `cmd/pwc_to_dbt.py`:

```bash
# only needed if you're working outside of the container in a venv (in container's isolated invironment everything is set up for the project only)
source .venv/bin/activate

python cmd/pwc_to_dbt.py inventory FLOWLINE_DEMO_JAFFLESHOP.xml
python cmd/pwc_to_dbt.py graph FLOWLINE_DEMO_JAFFLESHOP.xml --mapping m_FL_JS_STAGING_FULL
python cmd/pwc_to_dbt.py generate FLOWLINE_DEMO_JAFFLESHOP.xml --output models/staging
python cmd/pwc_to_dbt.py model FLOWLINE_DEMO_JAFFLESHOP.xml m_FL_JS_STAGING_FULL STG_CUSTOMERS

# executes the WORKFLOW node (currently only TASKINSTANCE linked to SESSION nodes which have MAPPING related definitions)
# TODO: can be extended and enhanced to fully support the XML format with all nodes, commands, etc.
python cmd/pwc_to_dbt.py workflow FLOWLINE_DEMO_JAFFLESHOP.xml wf_FL_JAFFLESHOP_DEMO
python cmd/pwc_to_dbt.py workflow FLOWLINE_DEMO_JAFFLESHOP.xml wf_FL_JAFFLESHOP_DEMO --output models/staging

# writes XML-derived SOURCE metadata to models/sources.yml
python cmd/pwc_to_dbt.py sources FLOWLINE_DEMO_JAFFLESHOP.xml --output models/sources.yml

# to validate the structure of the XML file
python cmd/pwc_to_dbt.py validate FLOWLINE_DEMO_JAFFLESHOP.xml
```

The `generate` command writes one SQL file per mapping target and also writes
`models/sources.yml` from the XML `SOURCE` definitions. The `model`
command prints one generated model to the terminal, which is useful for
manually inspecting lineage and expressions. The `workflow` command resolves
session task instances and prints their mapping execution order; with
`--output`, it generates models in that workflow order.

# Flowline PowerCenter Demo

A single Informatica PowerCenter repository export as an XML file that translates it to a dbt model. Used for demo purposes only.

## Contents

The export contains one repository and folder (`FLOWLINE_DEMO_JAFFLESHOP`) targeting Oracle, with:

- **Sources** — `RAW_*` tables (customers, orders, items, products, supplies, stores) plus staged `STG_*` tables.
- **Targets** — staging tables (`STG_*`), core marts (`CUSTOMERS`, `ORDERS`, `ORDER_ITEMS`, `PRODUCTS`, `SUPPLIES`), and enriched marts (`CUSTOMER_360`, `ORDER_FINANCIALS`, `ORDER_ITEM_ENRICHED`, `PRODUCT_DAILY_PERFORMANCE`, `STORE_DAILY_KPIS`).
- **Mappings** — `m_FL_JS_STAGING_FULL`, `m_FL_JS_MARTS_CORE`, `m_FL_JS_MARTS_ENRICHED`.
- **Workflow** — `wf_FL_JAFFLESHOP_DEMO`, running the three mappings via sessions `s_FL_JS_STAGING_FULL`, `s_FL_JS_MARTS_CORE`, `s_FL_JS_MARTS_ENRICHED`.

The pipeline flows RAW → staging → core marts → enriched marts.

## Transformation graph

The parser exposes the complete mapping transformation graph as a single
project definition. It is built from the parsed in-memory model, so the graph
does not contain Jaffle Shop-specific logic:

```python
from pwc_parser import build_project_definition, parse_file

project_definition = build_project_definition(parse_file("FLOWLINE_DEMO_JAFFLESHOP.xml"))
mapping = project_definition["mappings"]["m_FL_JS_STAGING_FULL"]
```

Each mapping contains `transformations`, `instances`, `connectors`, `sources`,
`targets`, `attributes`, and `variables`. Transformation definitions contain
their type, ports, XML attributes, and table properties. Source and target
definitions are resolved using the corresponding mapping instance name;
connectors retain both endpoint instances and fields.

## dbt SQL generation

Generates one dbt model file per mapping target. It uses connector
lineage to build target columns, creates CTEs for transformation instances,
and represents all table dependencies with dbt `ref()` references:

```python
from pwc_parser import generate_dbt_models, parse_file

document = parse_file("FLOWLINE_DEMO_JAFFLESHOP.xml")
paths = generate_dbt_models(document, "models")
```

Or generate one target in memory:

```python
from pwc_parser import generate_model_sql, parse_file

document = parse_file("FLOWLINE_DEMO_JAFFLESHOP.xml")
mapping = document.find_mapping("m_FL_JS_STAGING_FULL")
sql = generate_model_sql(mapping, document, "STG_CUSTOMERS")
```

The generator currently handles source/pass-through lineage, expression
ports, common date expressions, and join conditions. More complex Informatica
transformations such as routers and aggregators require dialect-specific SQL
rules and are intended to be extended in the generator.

All generated inputs use dbt `ref()` dependencies. Relation names are derived
from the XML definition names, normalized for dbt, so `RAW_CUSTOMERS` becomes
`{{ ref('raw_customers') }}` and `STG_CUSTOMERS` becomes
`{{ ref('stg_customers') }}`. The converter does not inspect local seed files.

