from __future__ import annotations

from services.agent.utils.parsers.tuple import parse_tuple


class TestParseTupleValid:
    """Valid inputs that should return a 6-tuple."""

    def test_with_parens(self):
        assert parse_tuple("(1,0,1,0,0,0)") == (1, 0, 1, 0, 0, 0)

    def test_without_parens(self):
        assert parse_tuple("1,0,1,0,0,0") == (1, 0, 1, 0, 0, 0)

    def test_with_spaces(self):
        assert parse_tuple("( 1 , 0 , 1 , 0 , 0 , 0 )") == (1, 0, 1, 0, 0, 0)

    def test_leading_trailing_whitespace(self):
        assert parse_tuple("  (1,0,1,0,0,0)  ") == (1, 0, 1, 0, 0, 0)

    def test_all_zeros(self):
        assert parse_tuple("(0,0,0,0,0,0)") == (0, 0, 0, 0, 0, 0)

    def test_large_values(self):
        assert parse_tuple("(100,200,300,400,500,600)") == (100, 200, 300, 400, 500, 600)


class TestParseTupleInvalid:
    """Invalid inputs that should return None."""

    def test_wrong_length_too_few(self):
        assert parse_tuple("(1,0,1,0,0)") is None

    def test_wrong_length_too_many(self):
        assert parse_tuple("(1,0,1,0,0,0,0)") is None

    def test_negative_value(self):
        assert parse_tuple("(1,-1,1,0,0,0)") is None

    def test_non_numeric(self):
        assert parse_tuple("(a,b,c,d,e,f)") is None

    def test_mixed_non_numeric(self):
        assert parse_tuple("(1,0,foo,0,0,0)") is None

    def test_empty_string(self):
        assert parse_tuple("") is None

    def test_float_values(self):
        assert parse_tuple("(1.5,0,1,0,0,0)") is None

    def test_completely_garbage(self):
        assert parse_tuple("hello world") is None

    def test_single_value(self):
        assert parse_tuple("42") is None
