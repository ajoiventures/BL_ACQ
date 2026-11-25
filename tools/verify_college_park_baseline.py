"""Verify the published College Park observatory against retained source receipts."""
import json
from pathlib import Path

from backend.core.college_park_baseline import DIRECTORY, load_verified_baseline


def verify(root=Path.cwd()):
    _, verification = load_verified_baseline(root)
    return verification


if __name__ == "__main__":
    print(json.dumps(verify(), indent=2))
