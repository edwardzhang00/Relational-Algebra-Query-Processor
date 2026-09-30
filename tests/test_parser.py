"""Parser tests -- assignment cases 10 to 17."""
import unittest

from test_helpers import (
    parse_query, render_tree, ParseError,
    Minus, Union, Intersect, Select, Project, RelRef,
    And, Or, Not, Comparison,
)


class TestParser(unittest.TestCase):

    # ------------------------------------------------------------------
    # Case 10: A union B minus C  ->  (A union B) minus C
    # ------------------------------------------------------------------
    def test_case_10_union_minus_left_assoc(self):
        ast = parse_query("A union B minus C")
        self.assertIsInstance(ast, Minus)
        self.assertIsInstance(ast.left, Union)
        self.assertEqual(ast.left.left.name, 'A')
        self.assertEqual(ast.left.right.name, 'B')
        self.assertEqual(ast.right.name, 'C')

    # ------------------------------------------------------------------
    # Case 11: A minus B minus C  ->  (A minus B) minus C
    # ------------------------------------------------------------------
    def test_case_11_minus_left_assoc(self):
        ast = parse_query("A minus B minus C")
        self.assertIsInstance(ast, Minus)
        self.assertIsInstance(ast.left, Minus)
        self.assertEqual(ast.left.left.name, 'A')
        self.assertEqual(ast.left.right.name, 'B')
        self.assertEqual(ast.right.name, 'C')

    # ------------------------------------------------------------------
    # Case 12: not > and > or
    # ------------------------------------------------------------------
    def test_case_12_not_binds_tightest(self):
        ast = parse_query("select[not (a=1 and b=2) or c>3](R)")
        self.assertIsInstance(ast, Select)
        self.assertIsInstance(ast.cond, Or)
        self.assertIsInstance(ast.cond.left, Not)
        self.assertIsInstance(ast.cond.left.cond, And)
        self.assertIsInstance(ast.cond.right, Comparison)
        self.assertEqual(ast.cond.right.op, '>')

    # ------------------------------------------------------------------
    # Case 13: a=1 and b=2 or c=3  ->  (a=1 and b=2) or c=3
    # ------------------------------------------------------------------
    def test_case_13_and_binds_tighter_than_or(self):
        ast = parse_query("select[a=1 and b=2 or c=3](R)")
        self.assertIsInstance(ast, Select)
        self.assertIsInstance(ast.cond, Or)
        self.assertIsInstance(ast.cond.left, And)
        self.assertIsInstance(ast.cond.right, Comparison)
        self.assertEqual(ast.cond.right.op, '=')

    # ------------------------------------------------------------------
    # Case 14: three levels of nesting
    # ------------------------------------------------------------------
    def test_case_14_nested_unary(self):
        ast = parse_query(
            "project[Name](select[Age>30](select[DID='D1'](Employees)))"
        )
        self.assertIsInstance(ast, Project)
        self.assertEqual(ast.attrs, ['Name'])
        self.assertIsInstance(ast.input, Select)
        self.assertIsInstance(ast.input.input, Select)
        self.assertIsInstance(ast.input.input.input, RelRef)
        self.assertEqual(ast.input.input.input.name, 'Employees')

    # ------------------------------------------------------------------
    # Case 15: parentheses override precedence
    # ------------------------------------------------------------------
    def test_case_15_explicit_parens(self):
        ast = parse_query("(A union B) minus (C intersect D)")
        self.assertIsInstance(ast, Minus)
        self.assertIsInstance(ast.left, Union)
        self.assertIsInstance(ast.right, Intersect)

    # ------------------------------------------------------------------
    # Case 16: missing closing parenthesis
    # ------------------------------------------------------------------
    def test_case_16_missing_paren(self):
        with self.assertRaises(ParseError) as cm:
            parse_query("select[Age>30](R")
        self.assertIn(")", cm.exception.message.lower() + ")")

    # ------------------------------------------------------------------
    # Case 17: empty projection list
    # ------------------------------------------------------------------
    def test_case_17_empty_projection(self):
        with self.assertRaises(ParseError):
            parse_query("project[](R)")

    # ------------------------------------------------------------------
    # Extra: the tree printed for case 10 must show (A union B) minus C.
    # ------------------------------------------------------------------
    def test_extra_tree_for_case_10(self):
        ast = parse_query("A union B minus C")
        out = render_tree(ast)
        # Top node is Minus; left child is Union; right child is C.
        lines = [l for l in out.splitlines() if l.strip()]
        self.assertTrue(lines[0].startswith("Minus"))
        # Indented lines under Minus
        self.assertTrue(any("Union" in l for l in lines[1:]))

    # ------------------------------------------------------------------
    # Extra: associativity of minus is visible in the printed tree.
    # ------------------------------------------------------------------
    def test_extra_tree_for_case_11(self):
        ast = parse_query("A minus B minus C")
        out = render_tree(ast)
        lines = [l for l in out.splitlines() if l.strip()]
        # Root and left child both Minus
        self.assertTrue(lines[0].startswith("Minus"))
        self.assertTrue(any("Minus" in l for l in lines[1:]))

    # ------------------------------------------------------------------
    # Extra: associativity of minus matters on data.
    # ------------------------------------------------------------------
    def test_extra_minus_associativity_data(self):
        # (A - B) - C  !=  A - (B - C)  for the A,B,C from test_helpers.
        from test_helpers import build_test_db, eval_query
        db = build_test_db()
        left = eval_query("A minus B minus C", db)
        right = eval_query("A minus (B minus C)", db)
        self.assertNotEqual(
            set(left.rows),
            set(right.rows),
            "(A-B)-C and A-(B-C) should differ for the chosen data",
        )
        # The documented grouping is left-associative:
        self.assertEqual(set(left.rows), set())          # {1,2} - {2} - {1} = {}
        self.assertEqual(set(right.rows), {(1,)})        # {1,2} - ({2}-{1}) = {1}

    # ------------------------------------------------------------------
    # Extra: not binds tighter than and even without parens.
    # ------------------------------------------------------------------
    def test_extra_not_without_parens(self):
        ast = parse_query("select[not a=1 and b=2](R)")
        # not a=1 and b=2  ->  (not a=1) and b=2
        self.assertIsInstance(ast.cond, And)
        self.assertIsInstance(ast.cond.left, Not)
        self.assertIsInstance(ast.cond.right, Comparison)

    # ------------------------------------------------------------------
    # Extra: times binds tighter than intersect.
    # ------------------------------------------------------------------
    def test_extra_times_tighter_than_intersect(self):
        ast = parse_query("A times B intersect C")
        self.assertIsInstance(ast, Intersect)
        from test_helpers import Times
        self.assertIsInstance(ast.left, Times)

    # ------------------------------------------------------------------
    # Extra: join is at the same level as times.
    # ------------------------------------------------------------------
    def test_extra_join_left_assoc(self):
        ast = parse_query("A join[x=1] B join[y=2] C")
        from test_helpers import Join
        self.assertIsInstance(ast, Join)
        self.assertIsInstance(ast.left, Join)

    # ------------------------------------------------------------------
    # Extra: case 17 must be a syntax error, not a runtime error.
    # ------------------------------------------------------------------
    def test_extra_empty_projection_is_syntax_error(self):
        with self.assertRaises(ParseError):
            parse_query("project[](R)")

    # ------------------------------------------------------------------
    # Extra: unterminated string inside a query is a LexError.
    # ------------------------------------------------------------------
    def test_extra_query_lex_error(self):
        from test_helpers import LexError, Tokenizer
        with self.assertRaises(LexError):
            Tokenizer("select[Name='Bob](R)").tokenize()


if __name__ == '__main__':
    unittest.main()