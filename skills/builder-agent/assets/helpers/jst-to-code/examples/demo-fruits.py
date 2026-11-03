#!/usr/bin/env python3
"""Replaces the "demo-fruits" transformation. Removes "orange" (any case) from a list of
fruits and uppercases the rest.

INPUT (1 variable):
  fruits     array of strings
OUTPUT (2 variables):
  info       object {originalSize, newSize}
  newFruits  array of strings
"""
import sys
import json


def main():
    data = json.load(sys.stdin)
    fruits = data["fruits"]

    # method 1 -- Array.filter(fruits, f_query_1): drop case-insensitive "orange"
    filtered = [e for e in fruits if e.lower() != "orange"]

    # method 3 -- Array.map(filtered, f_map_1): uppercase each survivor
    new_fruits = [e.upper() for e in filtered]

    # method 5 -- Array.length(new_fruits)
    new_size = len(new_fruits)

    # method 9 -- Array.length(fruits)  (original, independent of the filter chain)
    original_size = len(fruits)

    # outgoing assembly, keyed by $id; `info` built from its two pointer sub-paths
    result = {
        "info": {"originalSize": original_size, "newSize": new_size},
        "newFruits": new_fruits,
    }
    print(json.dumps(result))


if __name__ == "__main__":
    main()
