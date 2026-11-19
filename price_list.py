import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
PRIVATE_PRICE_LIST = ROOT / "private" / "price-list.json"
EXAMPLE_PRICE_LIST = ROOT / "price-list.example.json"


def load_price_list(path=None):
    if path is None:
        path = PRIVATE_PRICE_LIST if PRIVATE_PRICE_LIST.is_file() else EXAMPLE_PRICE_LIST
    data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    for section in data["sections"]:
        for item in section["items"]:
            for key in ("rub", "stars"):
                if type(item[key]) is not int or item[key] <= 0:
                    raise ValueError("Price list amounts must be positive integers")
            if not isinstance(item["name"], str) or not 0 < len(item["name"]) <= 64:
                raise ValueError("Price list names must contain 1 to 64 characters")
    return data


def format_price_section(section):
    lines = [section["title"]]
    prefixes = {"from": "от ", "addon": "+"}
    for item in section["items"]:
        prefix = prefixes.get(item.get("type"), "")
        lines.append(f"{item['name']} — {prefix}{item['rub']} ₽ / {prefix}{item['stars']} ⭐")
    return "\n".join(lines)
