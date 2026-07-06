from src.domain.enums import Act


def test_act_has_all_http_methods():
    assert Act.POST.value == "POST"
    assert Act.GET.value == "GET"
    assert Act.PATCH.value == "PATCH"
    assert Act.DELETE.value == "DELETE"


def test_act_is_str_enum():
    assert isinstance(Act.POST, str)
    assert Act.POST == "POST"


def test_act_members_count():
    assert len(list(Act)) == 4
