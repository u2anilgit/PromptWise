import pytest
from promptwise_v2.core.skill_validator import SkillValidator


@pytest.fixture
def validator():
    return SkillValidator()


@pytest.fixture
def simple_schema():
    return {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "count": {"type": "integer"},
        },
        "required": ["name"],
    }


def test_valid_data_passes(validator, simple_schema):
    """Valid data conforming to schema returns (True, '')."""
    ok, msg = validator.validate("my_skill", {"name": "test", "count": 5}, simple_schema)
    assert ok is True
    assert msg == ""


def test_invalid_type_fails(validator, simple_schema):
    """Wrong type for a field returns (False, non-empty message)."""
    ok, msg = validator.validate("my_skill", {"name": 42, "count": 5}, simple_schema)
    assert ok is False
    assert len(msg) > 0


def test_missing_required_field_fails(validator, simple_schema):
    """Missing required field returns (False, non-empty message)."""
    ok, msg = validator.validate("my_skill", {"count": 3}, simple_schema)
    assert ok is False
    assert len(msg) > 0


def test_none_schema_passthrough(validator):
    """schema=None always returns (True, '') regardless of data."""
    ok, msg = validator.validate("any_skill", {"anything": "goes"}, None)
    assert ok is True
    assert msg == ""


def test_valid_empty_dict_no_required(validator):
    """Empty dict passes a schema that has no required fields."""
    schema = {
        "type": "object",
        "properties": {
            "optional_field": {"type": "string"},
        },
    }
    ok, msg = validator.validate("my_skill", {}, schema)
    assert ok is True
    assert msg == ""
