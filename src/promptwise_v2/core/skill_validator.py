import jsonschema


class SkillValidator:
    """Validates skill output data against a JSON Schema."""

    def validate(self, skill_name: str, output_data: dict, schema: dict | None) -> tuple[bool, str]:
        """Validate output_data against jsonschema schema.

        Returns (True, "") on success.
        Returns (False, error_message) on failure.
        If schema is None, returns (True, "") — no schema = no validation.
        """
        if schema is None:
            return (True, "")

        try:
            jsonschema.validate(instance=output_data, schema=schema)
            return (True, "")
        except jsonschema.ValidationError as e:
            return (False, str(e.message))
        except Exception as e:
            return (False, f"Validation error: {str(e)}")
