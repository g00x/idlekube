import json


def write_json(data: dict, output_path: str | None) -> None:
    text = json.dumps(data, indent=2)
    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(text)
    else:
        print(text)
