import jsonschema


class SkillValidator:
    def validate(self, skill_name: str, output_data: dict, schema: dict | None) -> tuple[bool, str]:
        if schema is None:
            return True, ""
        try:
            jsonschema.validate(instance=output_data, schema=schema)
            return True, ""
        except jsonschema.ValidationError as e:
            return False, str(e.message)
        except Exception as e:
            return False, f"Validation error: {str(e)}"
