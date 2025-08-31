import json
import ast
from fuzzywuzzy import fuzz


def safe_parse_json_or_python(s):
    """Try parsing as JSON first, then as Python literal."""
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        try:
            return ast.literal_eval(s)
        except Exception as err:
            raise err


def fast_fuzzy(text1, text2):
    """Good balance of speed and typo tolerance"""
    return fuzz.ratio(text1, text2) / 100  # Normalize to 0-1