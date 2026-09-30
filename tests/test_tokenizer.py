"""Tokenizer tests -- assignment cases 1 to 9."""
import unittest

from test_helpers import tokenize_query, LexError, Tokenizer


class TestTokenizer(unittest.TestCase):

    # ------------------------------------------------------------------
    # Case 1: no whitespace at all.
    # ------------------------------------------------------------------
    def test_case_01_no_whitespace(self):
        toks = tokenize_query("select[x1=3](R)")
        self.assertEqual(
            [t.kind for t in toks],
            ['KEYWORD', 'SYMBOL', 'IDENT', 'SYMBOL', 'INTEGER',
             'SYMBOL', 'SYMBOL', 'IDENT', 'SYMBOL'],
        )
        self.assertEqual(
            [t.value for t in toks],
            ['select', '[', 'x1', '=', 3, ']', '(', 'R', ')'],
        )

    # ------------------------------------------------------------------
    # Case 2: whitespace between tokens produces the same tokens.
    # ------------------------------------------------------------------
    def test_case_02_whitespace_irrelevant(self):
        a = tokenize_query("select[x1=3](R)")
        b = tokenize_query("select[ x1 = 3 ](R)")
        self.assertEqual(
            [(t.kind, t.value) for t in a],
            [(t.kind, t.value) for t in b],
        )

    # ------------------------------------------------------------------
    # Case 3: '>=' is one token.
    # ------------------------------------------------------------------
    def test_case_03_geq_single_token(self):
        toks = tokenize_query("select[Age>=30](R)")
        ge = [t for t in toks if t.value == '>=']
        self.assertEqual(len(ge), 1)
        self.assertEqual(ge[0].kind, 'SYMBOL')
        # No bare '>' left behind
        self.assertFalse(any(t.value == '>' for t in toks))
        # No bare '=' left behind
        self.assertFalse(any(t.value == '=' for t in toks))

    # ------------------------------------------------------------------
    # Case 4: maximal munch must not invent a '>-' operator.
    # ------------------------------------------------------------------
    def test_case_04_gt_negative_number(self):
        toks = tokenize_query("select[Age>-30](R)")
        self.assertFalse(any(t.value == '>-' for t in toks))
        gt = [t for t in toks if t.value == '>']
        self.assertEqual(len(gt), 1)
        neg = [t for t in toks if t.kind == 'INTEGER']
        self.assertEqual(neg, [t for t in neg])  # exactly one integer
        self.assertEqual(len(neg), 1)
        self.assertEqual(neg[0].value, -30)

    # ------------------------------------------------------------------
    # Case 5: a parenthesis inside a string does not close anything.
    # ------------------------------------------------------------------
    def test_case_05_paren_inside_string(self):
        toks = tokenize_query("select[Name='Bob)'](R)")
        strings = [t for t in toks if t.kind == 'STRING']
        self.assertEqual(len(strings), 1)
        self.assertEqual(strings[0].value, 'Bob)')
        # The real ')' still appears as a symbol
        self.assertTrue(any(t.kind == 'SYMBOL' and t.value == ')'
                            for t in toks))

    # ------------------------------------------------------------------
    # Case 6: a comma inside a string does not separate anything.
    # ------------------------------------------------------------------
    def test_case_06_comma_inside_string(self):
        toks = tokenize_query("select[Name='a,b'](R)")
        strings = [t for t in toks if t.kind == 'STRING']
        self.assertEqual(len(strings), 1)
        self.assertEqual(strings[0].value, 'a,b')
        # No comma symbol outside the string
        self.assertFalse(any(t.kind == 'SYMBOL' and t.value == ','
                             for t in toks))

    # ------------------------------------------------------------------
    # Case 7: doubled quote inside a quoted string.
    # ------------------------------------------------------------------
    def test_case_07_doubled_quote(self):
        toks = tokenize_query("select[Name='O''Brien'](R)")
        strings = [t for t in toks if t.kind == 'STRING']
        self.assertEqual(len(strings), 1)
        self.assertEqual(strings[0].value, "O'Brien")

    # ------------------------------------------------------------------
    # Case 8: a keyword may be used as an attribute name.
    # ------------------------------------------------------------------
    def test_case_08_keyword_as_identifier(self):
        toks = tokenize_query("select[union=3](R)")
        union_tok = [t for t in toks if t.value == 'union']
        self.assertEqual(len(union_tok), 1)
        # The tokenizer still classifies it as KEYWORD; the *parser*
        # resolves it to an identifier in operand position.
        self.assertEqual(union_tok[0].kind, 'KEYWORD')

    # ------------------------------------------------------------------
    # Case 9: unterminated string is a lexical error with a position.
    # ------------------------------------------------------------------
    def test_case_09_unterminated_string(self):
        with self.assertRaises(LexError) as cm:
            Tokenizer("select[Name='Bob](R)").tokenize()
        e = cm.exception
        # Opening quote is at index 12 in "select[Name='Bob](R)"
        self.assertEqual(e.start, 12)
        self.assertEqual(e.line, 1)
        self.assertEqual(e.col, 13)
        self.assertIn("Unterminated", e.message)

    # ------------------------------------------------------------------
    # Extra: '<=' and '!=' are single tokens.
    # ------------------------------------------------------------------
    def test_extra_leq_single_token(self):
        toks = tokenize_query("select[x<=1](R)")
        leq = [t for t in toks if t.value == '<=']
        self.assertEqual(len(leq), 1)

    def test_extra_neq_single_token(self):
        toks = tokenize_query("select[x!=1](R)")
        neq = [t for t in toks if t.value == '!=']
        self.assertEqual(len(neq), 1)

    # ------------------------------------------------------------------
    # Extra: a lone '!' is a lexical error.
    # ------------------------------------------------------------------
    def test_extra_lone_bang(self):
        with self.assertRaises(LexError):
            Tokenizer("select[x!1](R)").tokenize()

    # ------------------------------------------------------------------
    # Extra: a '-' not followed by a digit is a lexical error.
    # ------------------------------------------------------------------
    def test_extra_lone_minus(self):
        with self.assertRaises(LexError):
            Tokenizer("select[x>- 1](R)").tokenize()

    # ------------------------------------------------------------------
    # Extra: positions are recorded.
    # ------------------------------------------------------------------
    def test_extra_token_positions(self):
        toks = tokenize_query("select[x=1](R)")
        # select at col 1, '[' at col 7, x at col 8, '=' at col 9,
        # 1 at col 10, ']' at col 11
        self.assertEqual(toks[0].col, 1)
        self.assertEqual(toks[1].col, 7)
        self.assertEqual(toks[2].col, 8)
        self.assertEqual(toks[3].col, 9)
        self.assertEqual(toks[4].col, 10)
        self.assertEqual(toks[5].col, 11)


if __name__ == '__main__':
    unittest.main()