from pwc_parser import build_workflow_definition, parse_string, workflow_execution_plan


XML = """
<ROOT>
  <FOLDER NAME="DEMO">
    <MAPPING NAME="m_stage" />
    <MAPPING NAME="m_core" />
    <SESSION NAME="s_stage" MAPPINGNAME="m_stage" REUSABLE="YES" />
    <WORKFLOW NAME="wf_demo">
      <SESSION NAME="s_core" MAPPINGNAME="m_core" REUSABLE="NO" />
      <TASKINSTANCE NAME="Start" TASKNAME="Start" TASKTYPE="Start" />
      <TASKINSTANCE NAME="s_stage" TASKNAME="s_stage" TASKTYPE="Session" />
      <TASKINSTANCE NAME="s_core" TASKNAME="s_core" TASKTYPE="Session" />
      <WORKFLOWLINK FROMTASK="Start" TOTASK="s_stage" />
      <WORKFLOWLINK FROMTASK="s_stage" TOTASK="s_core" />
    </WORKFLOW>
  </FOLDER>
</ROOT>
"""


def test_workflow_resolves_sessions_and_mappings_in_dependency_order():
    document = parse_string(XML)
    workflow = document.find_workflow("wf_demo")

    plan = workflow_execution_plan(workflow, document)
    assert [(session.name, session.mapping_name) for session in plan] == [
        ("s_stage", "m_stage"),
        ("s_core", "m_core"),
    ]
    assert build_workflow_definition(workflow, document)["execution_plan"] == [
        {"session": "s_stage", "mapping": "m_stage"},
        {"session": "s_core", "mapping": "m_core"},
    ]
