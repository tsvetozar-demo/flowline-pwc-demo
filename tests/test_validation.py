from pwc_parser import parse_string, validate_document


def test_validation_reports_dangling_mapping_references():
    document = parse_string("""
    <ROOT><FOLDER NAME="F">
      <MAPPING NAME="m">
        <INSTANCE NAME="EXP" TRANSFORMATION_NAME="MISSING" TYPE="TRANSFORMATION" />
        <CONNECTOR FROMINSTANCE="EXP" FROMFIELD="x" TOINSTANCE="NOPE" TOFIELD="y" />
      </MAPPING>
    </FOLDER></ROOT>
    """)

    codes = {issue.code for issue in validate_document(document)}
    assert {"UNKNOWN_TRANSFORMATION", "UNKNOWN_INSTANCE", "UNKNOWN_PORT"} <= codes


def test_validation_reports_unknown_workflow_session_and_mapping():
    document = parse_string("""
    <ROOT><FOLDER NAME="F">
      <SESSION NAME="s" MAPPINGNAME="MISSING" />
      <WORKFLOW NAME="wf">
        <TASKINSTANCE NAME="s" TASKNAME="s" TASKTYPE="Session" />
        <TASKINSTANCE NAME="other" TASKNAME="other" TASKTYPE="Session" />
        <WORKFLOWLINK FROMTASK="s" TOTASK="missing_task" />
      </WORKFLOW>
    </FOLDER></ROOT>
    """)

    codes = {issue.code for issue in validate_document(document)}
    assert {"UNKNOWN_MAPPING", "UNKNOWN_SESSION", "UNKNOWN_TASK"} <= codes


def test_validation_accepts_sample_document():
    from pwc_parser import parse_file

    assert validate_document(parse_file("FLOWLINE_DEMO_JAFFLESHOP.xml")) == ()
