from pwc_parser import build_project_definition, generate_dbt_models, generate_model_sql, parse_file, parse_string


XML = """
<ROOT>
  <FOLDER NAME="DEMO">
    <SOURCE NAME="RAW_CUSTOMERS">
      <SOURCEFIELD NAME="ID" DATATYPE="string" />
    </SOURCE>
    <TARGET NAME="CUSTOMERS">
      <TARGETFIELD NAME="CUSTOMER_ID" DATATYPE="string" />
    </TARGET>
    <MAPPING NAME="m_customers">
      <TRANSFORMATION NAME="EXP_CUSTOMERS" TYPE="Expression">
        <TRANSFORMFIELD NAME="CUSTOMER_ID" PORTTYPE="OUTPUT" EXPRESSION="ID" />
        <TABLEATTRIBUTE NAME="Some Property" VALUE="Some Value" />
      </TRANSFORMATION>
      <INSTANCE NAME="RAW_CUSTOMERS_1" TRANSFORMATION_NAME="RAW_CUSTOMERS" TRANSFORMATION_TYPE="Source Definition" TYPE="SOURCE" />
      <INSTANCE NAME="EXP_CUSTOMERS_1" TRANSFORMATION_NAME="EXP_CUSTOMERS" TRANSFORMATION_TYPE="Expression" TYPE="TRANSFORMATION" />
      <INSTANCE NAME="CUSTOMERS_1" TRANSFORMATION_NAME="CUSTOMERS" TRANSFORMATION_TYPE="Target Definition" TYPE="TARGET" />
      <CONNECTOR FROMINSTANCE="RAW_CUSTOMERS_1" FROMFIELD="ID" TOINSTANCE="EXP_CUSTOMERS_1" TOFIELD="ID" />
      <CONNECTOR FROMINSTANCE="EXP_CUSTOMERS_1" FROMFIELD="CUSTOMER_ID" TOINSTANCE="CUSTOMERS_1" TOFIELD="CUSTOMER_ID" />
    </MAPPING>
  </FOLDER>
</ROOT>
"""


def test_project_definition_resolves_graph_nodes_and_edges():
    graph = build_project_definition(parse_string(XML))["mappings"]["m_customers"]

    assert graph["transformations"]["EXP_CUSTOMERS"]["type"] == "Expression"
    assert graph["transformations"]["EXP_CUSTOMERS"]["ports"]["CUSTOMER_ID"]["EXPRESSION"] == "ID"
    assert graph["transformations"]["EXP_CUSTOMERS"]["attributes"]["Some Property"] == "Some Value"
    assert graph["instances"]["EXP_CUSTOMERS_1"]["definition_name"] == "EXP_CUSTOMERS"
    assert graph["sources"]["RAW_CUSTOMERS_1"]["ports"]["ID"]["NAME"] == "ID"
    assert graph["targets"]["CUSTOMERS_1"]["ports"]["CUSTOMER_ID"]["NAME"] == "CUSTOMER_ID"
    assert len(graph["connectors"]) == 2


def test_mapping_graph_can_be_built_without_repository_definitions():
    mapping = parse_string("<ROOT><FOLDER><MAPPING NAME='m'><TRANSFORMATION NAME='T' TYPE='Expression'/></MAPPING></FOLDER></ROOT>").mappings[0]
    assert mapping.graph()["transformations"]["T"]["type"] == "Expression"


def test_mapping_generates_dbt_sql_from_connector_lineage():
    document = parse_string(XML)
    sql = generate_model_sql(document.mappings[0], document, "CUSTOMERS_1")

    assert "{{ ref('raw_customers') }}" in sql
    assert "    ID AS CUSTOMER_ID" not in sql
    assert "i0.ID AS CUSTOMER_ID" in sql


def test_mapping_generation_writes_dbt_model_files(tmp_path):
    document = parse_string(XML)

    paths = generate_dbt_models(document, tmp_path)

    assert [path.name for path in paths] == ["customers.sql"]
    assert "SELECT" in paths[0].read_text(encoding="utf-8")
    assert "{{ ref('raw_customers') }}" in paths[0].read_text(encoding="utf-8")


def test_intermediate_definitions_use_dbt_ref():
    document = parse_string(XML.replace("RAW_CUSTOMERS", "STG_CUSTOMERS"))
    sql = generate_model_sql(document.mappings[0], document, "CUSTOMERS_1")

    assert "{{ ref('stg_customers') }}" in sql


def test_multiple_transformation_ctes_are_comma_separated():
    document = parse_file("FLOWLINE_DEMO_JAFFLESHOP.xml")
    mapping = document.find_mapping("m_FL_JS_STAGING_FULL")
    sql = generate_model_sql(mapping, document, "STG_PRODUCTS")
    assert ")\n\nexp_products AS (" not in sql
    assert "),\n\nexp_products AS (" in sql
    assert not sql.rstrip().endswith(";")


def test_generation_does_not_require_intermediate_sources_file(tmp_path):
    document = parse_file("FLOWLINE_DEMO_JAFFLESHOP.xml")

    paths = generate_dbt_models(document, tmp_path)

    assert not any(path.name == "sources.yml" for path in paths)
