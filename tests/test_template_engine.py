from src.personalization.template_engine import render_template


def test_full_data_no_missing_vars():
    template = "{first_name} Regarding {business_name} in {city}."
    result = render_template(
        template,
        {"first_name": "Hi John,", "business_name": "ABC Plumbing", "city": "Houston"},
    )
    assert "ABC Plumbing" in result.rendered_body
    assert "Houston" in result.rendered_body
    assert result.missing_variables == []
    assert result.used_fallback_greeting is False


def test_missing_owner_name_uses_fallback():
    template = "{first_name} Regarding {business_name}."
    result = render_template(
        template,
        {"first_name": None, "business_name": "Beyond Wow Plumbing"},
        fallback_greeting="Hi Beyond Wow Plumbing team,",
    )
    assert "Hi Beyond Wow Plumbing team," in result.rendered_body
    assert result.used_fallback_greeting is True
    assert result.modification_log is not None
    assert result.modification_log["reason"] == "missing_owner_name"


def test_unapproved_variable_left_untouched():
    template = "Hi {business_name}, your {secret_pricing} is great."
    result = render_template(template, {"business_name": "ABC Plumbing"})
    assert "{secret_pricing}" in result.rendered_body
    assert "secret_pricing" in result.missing_variables


def test_never_fabricates_name_when_missing():
    template = "{first_name}"
    result = render_template(template, {"first_name": None}, fallback_greeting="Hi there,")
    assert "Hi there," in result.rendered_body
    # Confirm no name-shaped text was invented
    assert result.rendered_body == "Hi there,"


if __name__ == "__main__":
    test_full_data_no_missing_vars()
    test_missing_owner_name_uses_fallback()
    test_unapproved_variable_left_untouched()
    test_never_fabricates_name_when_missing()
    print("All template_engine tests passed.")