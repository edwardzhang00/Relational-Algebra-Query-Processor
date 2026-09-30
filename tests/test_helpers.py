"""Shared helpers and test data for the test suite."""
import io
import os
import sys
from contextlib import redirect_stdout

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, '..'))
sys.path.insert(0, _HERE)

from ra import (  # noqa: E402
    Tokenizer, Parser, ProgramParser,
    build_db, eval_expr, reset_stats, STATS,
    print_tree, print_relation,
    LexError, ParseError, EvalError,
    NameError_, SchemaError, TypeMismatchError, DuplicateAttrError,
    Relation, Column,
    RelRef, Select, Project, Rename, Union, Intersect, Minus, Times, Join,
    Comparison, And, Or, Not, AttrRef, Integer, String,
)


# Relations used by the semantic tests.  Deliberately includes:
#  - Employees / Dept for cases 19, 22, 23, 24, 25
#  - Emp with MgrID for the self-join (case 20)
#  - R with A=B for case 18
#  - A, B, C with single attribute x for the ambiguity demo (cases 10, 11)
RELATIONS = """
Employees (EID, Name, Age, DID) = {
  E1, John, 32, D1
  E2, Alice, 28, D2
  E3, Bob, 29, D1
}

Dept (DID, DName) = {
  D1, Sales
  D2, Eng
}

Emp (EID, MgrID, DID) = {
  E1, E1, D1
  E2, E1, D2
  E3, E1, D1
}

R (A, B) = {
  1, 1
  2, 2
  3, 1
}

S (B, C) = {
  1, 10
  2, 20
}

A (x) = {
  1
  2
}

B (x) = {
  2
}

C (x) = {
  1
}
"""


def tokenize_query(text):
    """Tokenize a query string, dropping NEWLINE and EOF tokens."""
    return [t for t in Tokenizer(text).tokenize()
            if t.kind not in ('NEWLINE', 'EOF')]


def parse_query(text):
    """Parse a query string into an AST."""
    tokens = Tokenizer(text).tokenize()
    return Parser(tokens).parse_query()


def build_test_db():
    """Build the shared test database from RELATIONS."""
    tokens = Tokenizer(RELATIONS + "\nDummy\n").tokenize()
    prog = ProgramParser(tokens).parse_program()
    return build_db(prog)


def eval_query(query, db):
    """Parse and evaluate a query against an existing database."""
    ast = parse_query(query)
    reset_stats()
    return eval_expr(ast, db)


def render_tree(node):
    """Return the tree printed by print_tree as a string."""
    buf = io.StringIO()
    with redirect_stdout(buf):
        print_tree(node)
    return buf.getvalue()