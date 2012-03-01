import datetime

import billy.importers.filters as filters

def test_bookend_spaces():
    test_cases = {
        "Hello World"   : "Hello World",    # Sanity check.
        " Hello, World" : "Hello, World",   # Test leading space
        "Hello, World"  : "Hello, World",   # Test trailing space
        " Hello, World ": "Hello, World",   # Test both leading and trailing
        "Hello,   World" : "Hello,   World",# Test maintaining middle spaces

    }
    for case in test_cases:
        send = case
        get  = test_cases[case]
        got  = filters.strip_bookend_spaces(send)
        assert got == get

def test_remove_newlines():
    test_cases = {
        "Foo Bar"  : "Foo Bar", # Sanity
        "Foo\nBar" : "Foo Bar", # Inline Newline
        "Foo\n Bar": "Foo Bar", # Mixed double
        "Foo \nBar": "Foo Bar", # Mixed double, reversed
        "Foo  Bar" : "Foo Bar", # Double space
    }
    for case in test_cases:
        send = case
        get  = test_cases[case]
        got  = filters.remove_newlines(send)
        assert got == get
