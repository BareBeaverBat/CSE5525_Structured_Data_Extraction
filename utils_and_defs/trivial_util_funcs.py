import textwrap
from re import Pattern, Match
from typing import Optional


def d(multi_line_str: str) -> str:
    """
    abbreviation for removing superfluous start-of-line indenting from multi-line strings
    :param multi_line_str: a string value from a multi-line string expression
    :return: the multi-line string with any start-of-line whitespace that all lines have removed,
                plus any starting and ending newlines removed
    """
    return textwrap.dedent(multi_line_str).strip()


def find_last_re_match(regex: Pattern, text: str, start_pos: int = 0) -> Optional[Match]:
    """
    Finds the last match of the given regex in the given text
    :param regex: the compiled regex pattern to search for
    :param text: the text to search in
    :param start_pos: the starting position in the text to search from
    :return: the last match of the regex in the text, or None if no matches
    """
    matches = list(regex.finditer(text, start_pos))
    return matches[-1] if matches else None
