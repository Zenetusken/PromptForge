"""Update test passes status in feature_list.json."""
import json
import sys

# Usage: python update_tests.py <id1> <id2> ...
# Sets passes=true for given IDs

ids_to_pass = [int(x) for x in sys.argv[1:]]

with open("feature_list.json", "r") as f:
    tests = json.load(f)

updated = []
for test in tests:
    if test["id"] in ids_to_pass:
        test["passes"] = True
        updated.append(test["id"])

with open("feature_list.json", "w") as f:
    json.dump(tests, f, indent=2)
    f.write("\n")

print(f"Updated {len(updated)} tests to passes=true: {updated}")
