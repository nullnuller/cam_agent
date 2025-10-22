from cam_agent.utils.sources import extract_section, make_label, short_title


def test_short_title_mapping():
    assert short_title("APS-Code-of-Ethics.pdf") == "APS Code of Ethics"
    assert short_title("The-Act-2009-045.pdf") == "Health Practitioner Regulation National Law Act 2009"
    assert short_title("custom_doc.pdf") == "custom doc"


def test_extract_section_patterns():
    assert extract_section("Refer to APP 6.2(b) for guidance.") == "APP 6.2(b)"
    assert extract_section("See section 150 of the Act") == "section 150"
    assert extract_section("Clause A.5.2 applies.") == "A.5.2"
    assert extract_section("No clause here.") is None


def test_make_label_combines_title_and_clause():
    title = "Privacy Act 1988 (Cth) — Australian Privacy Principles (APPs)"
    passage = "Under APP 6.2(b), disclosures to enforcement bodies are permitted."
    assert make_label(title, passage) == "Privacy Act 1988 (Cth) — Australian Privacy Principles (APPs) — APP 6.2(b)"
