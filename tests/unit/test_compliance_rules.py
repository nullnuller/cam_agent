from cam_agent.compliance.rules import DISCLAIMER_HINT, evaluate_compliance
from cam_agent.services.types import ModelOutput, QueryRequest


def make_output(text: str) -> ModelOutput:
    return ModelOutput(
        text=text,
        model="test-model",
        prompt="prompt",
        retrieval_context="context",
        legend="legend",
        retrieved_hits=[],
        metadata={},
    )


def make_request(question: str = "test?") -> QueryRequest:
    return QueryRequest(user_id="u1", question=question)


def test_compliance_blocks_self_harm_instruction():
    output = make_output("You should harm yourself.")
    decision = evaluate_compliance(make_request(), output)
    assert decision.action == "block"
    assert any(issue.rule_id == "safety.no_suicide_instructions" for issue in decision.issues)


def test_compliance_warns_on_medication_directive():
    output = make_output("Stop taking your medicine immediately.")
    decision = evaluate_compliance(make_request(), output)
    assert decision.action == "warn"
    assert any(issue.rule_id == "safety.medication_directive" for issue in decision.issues)


def test_compliance_requires_disclaimer():
    output = make_output("Here is some guidance.")
    decision = evaluate_compliance(make_request(), output)
    assert any(issue.rule_id == "compliance.disclaimer_missing" for issue in decision.issues)
    assert decision.action == "warn"


def test_compliance_detects_existing_disclaimer():
    output = make_output("Seek professional advice before taking any action.")
    decision = evaluate_compliance(make_request(), output)
    assert all(issue.rule_id != "compliance.disclaimer_missing" for issue in decision.issues)

