import textwrap


def d(multi_line_str: str) -> str:
    """
    abbreviation for removing superfluous start-of-line indenting from multi-line strings
    :param multi_line_str: a string value from a multi-line string expression
    :return: the multi-line string with any start-of-line whitespace that all lines have removed,
                plus any starting and ending newlines removed
    """
    return textwrap.dedent(multi_line_str).strip()
