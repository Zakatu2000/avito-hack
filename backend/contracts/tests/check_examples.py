"""Validate the published operations and every referenced request/response fixture."""
import json
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator
from openapi_spec_validator import validate

ROOT = Path(__file__).resolve().parents[1]


def main():
    spec = yaml.safe_load((ROOT / "openapi.yaml").read_text(encoding="utf-8"))
    validate(spec)
    checked = set()
    for operations in spec["paths"].values():
        for operation in operations.values():
            bodies = list(operation["responses"].values())
            if "requestBody" in operation:
                bodies.append(operation["requestBody"])
            for body in bodies:
                media = body.get("content", {}).get("application/json")
                if not media:
                    continue
                validator = Draft202012Validator({
                    "components": spec["components"], **media["schema"]
                })
                for example in media.get("examples", {}).values():
                    path = (ROOT / example["externalValue"]).resolve()
                    validator.validate(json.loads(path.read_text(encoding="utf-8")))
                    checked.add(path)
    if checked != set((ROOT / "examples").glob("*.json")):
        raise ValueError("Есть примеры без привязки к операции")
    print(f"OpenAPI valid; {len(checked)} fixtures valid")


if __name__ == "__main__":
    main()
