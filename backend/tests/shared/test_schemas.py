from erp.shared.schemas import ApiSchema


class Sample(ApiSchema):
    company_name: str
    next_cursor: str | None = None


def test_dumps_camel_case_keys():
    dumped = Sample(company_name="Alpha").model_dump(mode="json")

    assert dumped == {"companyName": "Alpha", "nextCursor": None}


def test_accepts_camel_case_and_snake_case_input():
    assert Sample.model_validate({"companyName": "A"}).company_name == "A"
    assert Sample.model_validate({"company_name": "A"}).company_name == "A"
