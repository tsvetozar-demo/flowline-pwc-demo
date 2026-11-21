# Task

Build a small tool that converts an Informatica PowerCenter mapping into an equivalent dbt model. We have attached one sample PowerCenter mapping file in XML to work from.

An example file is FLOWLINE_DEMO_JAFFLESHOP.xml (but script should be able to parse any other XML file that defines the transformation).

The mapping mirrors the dbt jaffle shop demo project, which is public. You can use that project as a reference target: run it, look at its models, and check your converter's output against it. Build a converter that derives the dbt model from the XML. Do not hard-code the jaffle shop output, because we are assessing the conversion logic, not the final SQL.

# Layers

## Layer 1. Data transformation

### Layer 1, Step 1: Parse the XML file in memory in an easily navigated structure: pwc_parser

### Layer 1, Step 2: Build a graph of nodes of the transformation flow
    Essential nodes in XML file are the following:

    TRANSFORMATION  Defines transformation type, ports and expressions.
    INSTANCE        Identifies transformation/source/target usage in a mapping.
    CONNECTOR       Reconstructs data flow between ports.

    These nodes define the transformation flow from the original data to produce the final database result.

### Layer 1, Step 3: Execute mappings.
    The definitions in each <MAPPING> must be converted to SQL files.
    This means one function will locate all MAPPING nodes and for each will execute it based on the configuration nodes inside it.
    This needs to result in dbt model SQL files.


## Layer 2, Orchestration: parse the WORKFLOW functionality and process it

### Layer 2, Step 1: Process only TASKINSTANCE nodes that lead to executing SESSION and MAPPING
