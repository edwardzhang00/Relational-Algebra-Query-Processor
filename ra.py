#!/usr/bin/env python3
"""
Relational algebra engine: tokenizer, parser, evaluator.
Handles cases 1-25 from the assignment.
"""

import sys
from dataclasses import dataclass
from typing import Any, List, Optional, Set, Tuple, Dict

# ---------------------------------------------------------------------
# Instrumentation (Section 8.2)
# ---------------------------------------------------------------------
STATS = {
    "join_pairs":     0,   # pairs of tuples enumerated by times / join
    "select_tuples":  0,   # tuples examined by select
    "project_tuples": 0,   # tuples examined by project
}


def reset_stats():
    for k in STATS:
        STATS[k] = 0

# =====================================================================
# Tokenizer
# =====================================================================

KEYWORDS = {
    "select", "project", "rename",
    "union", "intersect", "minus", "times", "join",
    "and", "or", "not",
}

@dataclass
class Token:
    kind: str
    value: Any
    lexeme: str
    start: int
    line: int
    col: int
    end: int

    def __repr__(self):
        return f"Token({self.kind}, {self.value!r}, {self.line}:{self.col})"

class LexError(Exception):
    def __init__(self, message, start, line, col):
        self.message = message
        self.start = start
        self.line = line
        self.col = col
        super().__init__(f"{message} at line {line}, column {col} (index {start})")

def is_letter(ch):
    return ch == "_" or ("A" <= ch <= "Z") or ("a" <= ch <= "z")

def is_digit(ch):
    return "0" <= ch <= "9"

class Tokenizer:
    def __init__(self, text):
        self.text = text
        self.pos = 0
        self.line = 1
        self.col = 1
        self.length = len(text)

    def eof(self):
        return self.pos >= self.length

    def peek(self, offset=0):
        idx = self.pos + offset
        if idx >= self.length:
            return ""
        return self.text[idx]

    def advance(self):
        ch = self.text[self.pos]
        self.pos += 1
        if ch == "\n":
            self.line += 1
            self.col = 1
        else:
            self.col += 1
        return ch

    def add_token(self, kind, value, lexeme, start, line, col):
        return Token(kind, value, lexeme, start, line, col, self.pos)

    def tokenize(self) -> List[Token]:
        tokens: List[Token] = []
        brace_depth = 0

        while not self.eof():
            start = self.pos
            line = self.line
            col = self.col
            ch = self.peek()

            # 1. Whitespace except newline
            if ch in " \t\r":
                self.advance()
                continue

            # 2. Newline
            if ch == "\n":
                self.advance()
                tokens.append(
                    self.add_token("NEWLINE", "\n", "\n", start, line, col)
                )
                continue

            # 3. Comment
            if ch == "/" and self.peek(1) == "/":
                self.advance()
                self.advance()
                while not self.eof() and self.peek() != "\n":
                    self.advance()
                continue

            # 4. Quoted string
            if ch == "'":
                tokens.append(self.read_string(start, line, col))
                continue

            # 5. Open brace -- enter tuple-list context
            if ch == "{":
                self.advance()
                brace_depth += 1
                tokens.append(
                    self.add_token("SYMBOL", "{", "{", start, line, col)
                )
                continue

            # 6. Close brace -- leave tuple-list context
            if ch == "}":
                self.advance()
                brace_depth -= 1
                tokens.append(
                    self.add_token("SYMBOL", "}", "}", start, line, col)
                )
                continue

            # 7. Comma (valid in both contexts)
            if ch == ",":
                self.advance()
                tokens.append(
                    self.add_token("SYMBOL", ",", ",", start, line, col)
                )
                continue

            # 8. Inside a tuple list: read a bare value
            if brace_depth > 0:
                tokens.append(self.read_bare_value(start, line, col))
                continue

            # 9. Outside a tuple list: integer literal
            if is_digit(ch):
                tokens.append(self.read_integer(start, line, col))
                continue

            # 10. Negative integer literal or lexical error
            if ch == "-":
                if is_digit(self.peek(1)):
                    tokens.append(self.read_integer(start, line, col))
                    continue
                raise LexError(
                    "Unexpected '-' (not followed by a digit)", start, line, col
                )

            # 11. Identifier or keyword
            if is_letter(ch):
                tokens.append(self.read_ident_or_keyword(start, line, col))
                continue

            # 12. Two-character symbols
            two = ch + self.peek(1)
            if two in (">=", "<=", "!="):
                self.advance()
                self.advance()
                tokens.append(
                    self.add_token("SYMBOL", two, two, start, line, col)
                )
                continue

            # 13. Single-character symbols (braces and comma already handled)
            if ch in "()[]=<>.":
                self.advance()
                tokens.append(
                    self.add_token("SYMBOL", ch, ch, start, line, col)
                )
                continue

            # 14. A lone ! is a lexical error
            if ch == "!":
                raise LexError("Unexpected '!' (expected '!=')", start, line, col)

            raise LexError(f"Unexpected character {ch!r}", start, line, col)

        tokens.append(
            Token("EOF", None, "", self.pos, self.line, self.col, self.pos)
        )
        return tokens

    def read_string(self, start, line, col):
        self.advance()
        chars = []
        while True:
            if self.eof():
                raise LexError("Unterminated string literal", start, line, col)
            ch = self.peek()
            if ch == "'":
                if self.peek(1) == "'":
                    chars.append("'"); self.advance(); self.advance()
                else:
                    self.advance(); break
            else:
                chars.append(ch); self.advance()
        lexeme = self.text[start:self.pos]
        return self.add_token("STRING", "".join(chars), lexeme, start, line, col)

    def read_integer(self, start, line, col):
        if self.peek() == "-":
            self.advance()
        while is_digit(self.peek()):
            self.advance()
        lexeme = self.text[start:self.pos]
        value = int(lexeme)
        if value < -9223372036854775808 or value > 9223372036854775807:
            raise LexError(f"Integer literal out of signed 64-bit range: {lexeme}",
                           start, line, col)
        return self.add_token("INTEGER", value, lexeme, start, line, col)

    def read_ident_or_keyword(self, start, line, col):
        while True:
            ch = self.peek()
            if is_letter(ch) or is_digit(ch):
                self.advance()
            else:
                break
        lexeme = self.text[start:self.pos]
        kind = "KEYWORD" if lexeme in KEYWORDS else "IDENT"
        return self.add_token(kind, lexeme, lexeme, start, line, col)

    def read_bare_value(self, start: int, line: int, col: int) -> Token:
        """Read a bare value inside a tuple list.

        Reads until the next delimiter, then returns INTEGER if the
        lexeme is a well-formed integer literal, otherwise STRING.
        """
        chars: List[str] = []
        while not self.eof():
            ch = self.peek()
            if ch in _BARE_DELIMS:
                break
            # '//' starts a comment even inside a tuple list.
            if ch == "/" and self.peek(1) == "/":
                break
            chars.append(ch)
            self.advance()

        if not chars:
            raise LexError(
                f"Expected tuple value, got {self.peek()!r}", start, line, col
            )

        lexeme = "".join(chars)

        if looks_like_integer_literal(lexeme):
            try:
                value = int(lexeme)
            except ValueError:
                pass
            else:
                if value < -9223372036854775808 or value > 9223372036854775807:
                    raise LexError(
                        f"Integer literal out of signed 64-bit range: {lexeme}",
                        start,
                        line,
                        col,
                    )
                return self.add_token("INTEGER", value, lexeme, start, line, col)

        return self.add_token("STRING", lexeme, lexeme, start, line, col)
    
_BARE_DELIMS = set(" \t\r\n,(){}'")

def looks_like_integer_literal(s: str) -> bool:
    """True if s is an optional '-' followed by at least one digit."""
    if not s:
        return False
    if s[0] == "-":
        return len(s) > 1 and s[1:].isdigit()
    return s.isdigit()


# =====================================================================
# AST
# =====================================================================

class Node:
    def label(self): return self.__class__.__name__
    def children(self): return []

class RelRef(Node):
    def __init__(self, name): self.name = name
    def label(self): return f"Relation({self.name})"

class Select(Node):
    def __init__(self, cond, input): self.cond = cond; self.input = input
    def label(self): return f"Select(cond={self.cond.to_string()})"
    def children(self): return [self.input]

class Project(Node):
    def __init__(self, attrs, input): self.attrs = attrs; self.input = input
    def label(self): return f"Project(attrs=[{', '.join(self.attrs)}])"
    def children(self): return [self.input]

class Rename(Node):
    def __init__(self, new_name, input): self.new_name = new_name; self.input = input
    def label(self): return f"Rename({self.new_name})"
    def children(self): return [self.input]

class Union(Node):
    def __init__(self, l, r): self.left = l; self.right = r
    def label(self): return "Union"
    def children(self): return [self.left, self.right]

class Intersect(Node):
    def __init__(self, l, r): self.left = l; self.right = r
    def label(self): return "Intersect"
    def children(self): return [self.left, self.right]

class Minus(Node):
    def __init__(self, l, r): self.left = l; self.right = r
    def label(self): return "Minus"
    def children(self): return [self.left, self.right]

class Times(Node):
    def __init__(self, l, r): self.left = l; self.right = r
    def label(self): return "Times"
    def children(self): return [self.left, self.right]

class Join(Node):
    def __init__(self, cond, l, r): self.cond = cond; self.left = l; self.right = r
    def label(self): return f"Join(cond={self.cond.to_string()})"
    def children(self): return [self.left, self.right]

class Condition:
    def to_string(self): return ""

OP_NAMES = {"=": "Eq", "!=": "Neq", "<": "Lt", "<=": "Leq",
            ">": "Gt", ">=": "Geq"}

class Comparison(Condition):
    def __init__(self, op, l, r): self.op = op; self.left = l; self.right = r
    def to_string(self):
        return f"{OP_NAMES.get(self.op, self.op)}({self.left.to_string()}, {self.right.to_string()})"

class And(Condition):
    def __init__(self, l, r): self.left = l; self.right = r
    def to_string(self): return f"And({self.left.to_string()}, {self.right.to_string()})"

class Or(Condition):
    def __init__(self, l, r): self.left = l; self.right = r
    def to_string(self): return f"Or({self.left.to_string()}, {self.right.to_string()})"

class Not(Condition):
    def __init__(self, c): self.cond = c
    def to_string(self): return f"Not({self.cond.to_string()})"

class Operand:
    def to_string(self): return ""

class AttrRef(Operand):
    def __init__(self, relation, attr): self.relation = relation; self.attr = attr
    def to_string(self):
        return f"Attr({self.relation}.{self.attr})" if self.relation else f"Attr({self.attr})"

class Integer(Operand):
    def __init__(self, v): self.value = v
    def to_string(self): return f"Num({self.value})"

class String(Operand):
    def __init__(self, v): self.value = v
    def to_string(self): return f"Str({self.value!r})"

# Relation definition AST
class RelationDef:
    def __init__(self, name, attrs, tuples):
        self.name = name
        self.attrs = attrs
        self.tuples = tuples

class Program:
    def __init__(self, relations, query):
        self.relations = relations
        self.query = query


# =====================================================================
# Query Parser
# =====================================================================

class ParseError(Exception):
    def __init__(self, message, token):
        self.message = message
        self.token = token
        super().__init__(f"{message} at line {token.line}, column {token.col}")

class Parser:
    def __init__(self, tokens):
        self.tokens = [t for t in tokens if t.kind != "NEWLINE"]
        self.pos = 0

    def peek(self, offset=0):
        idx = self.pos + offset
        if idx >= len(self.tokens):
            return self.tokens[-1]
        return self.tokens[idx]

    def advance(self):
        t = self.peek()
        if t.kind != "EOF":
            self.pos += 1
        return t

    def expect(self, kind, value=None):
        t = self.peek()
        if t.kind != kind:
            raise ParseError(f"Expected {kind}, got {t.kind}", t)
        if value is not None and t.value != value:
            raise ParseError(f"Expected {value!r}, got {t.value!r}", t)
        return self.advance()

    def match(self, kind, value=None):
        t = self.peek()
        if t.kind == kind and (value is None or t.value == value):
            return self.advance()
        return None

    def is_ident_like(self, token):
        return token.kind in ("IDENT", "KEYWORD")

    def consume_ident_like(self):
        t = self.peek()
        if self.is_ident_like(t):
            return self.advance().value
        raise ParseError(f"Expected identifier, got {t.kind}", t)

    def parse_query(self):
        expr = self.parse_expr()
        if self.peek().kind != "EOF":
            raise ParseError("Unexpected token after query", self.peek())
        return expr

    def parse_expr(self):
        return self.parse_set_expr()

    def parse_set_expr(self):
        left = self.parse_intersect_expr()
        while True:
            t = self.peek()
            if t.kind == "KEYWORD" and t.value in ("union", "minus"):
                op = self.advance().value
                right = self.parse_intersect_expr()
                left = Union(left, right) if op == "union" else Minus(left, right)
            else:
                break
        return left

    def parse_intersect_expr(self):
        left = self.parse_times_join_expr()
        while True:
            t = self.peek()
            if t.kind == "KEYWORD" and t.value == "intersect":
                self.advance()
                right = self.parse_times_join_expr()
                left = Intersect(left, right)
            else:
                break
        return left

    def parse_times_join_expr(self):
        left = self.parse_unary_expr()
        while True:
            t = self.peek()
            if t.kind == "KEYWORD" and t.value == "times":
                self.advance()
                right = self.parse_unary_expr()
                left = Times(left, right)
            elif t.kind == "KEYWORD" and t.value == "join":
                if self.peek(1).kind == "SYMBOL" and self.peek(1).value == "[":
                    self.advance()
                    self.expect("SYMBOL", "[")
                    cond = self.parse_condition()
                    self.expect("SYMBOL", "]")
                    right = self.parse_unary_expr()
                    left = Join(cond, left, right)
                else:
                    break
            else:
                break
        return left

    def parse_unary_expr(self):
        t = self.peek()
        if t.kind == "KEYWORD":
            if t.value == "select" and self.peek(1).kind == "SYMBOL" and self.peek(1).value == "[":
                self.advance()
                self.expect("SYMBOL", "[")
                cond = self.parse_condition()
                self.expect("SYMBOL", "]")
                self.expect("SYMBOL", "(")
                inner = self.parse_expr()
                if not self.match("SYMBOL", ")"):
                    raise ParseError("Missing closing ')'", self.peek())
                return Select(cond, inner)
            if t.value == "project" and self.peek(1).kind == "SYMBOL" and self.peek(1).value == "[":
                self.advance()
                self.expect("SYMBOL", "[")
                attrs = self.parse_attr_list()
                self.expect("SYMBOL", "]")
                self.expect("SYMBOL", "(")
                inner = self.parse_expr()
                if not self.match("SYMBOL", ")"):
                    raise ParseError("Missing closing ')'", self.peek())
                return Project(attrs, inner)
            if t.value == "rename" and self.peek(1).kind == "SYMBOL" and self.peek(1).value == "[":
                self.advance()
                self.expect("SYMBOL", "[")
                new_name = self.consume_ident_like()
                self.expect("SYMBOL", "]")
                self.expect("SYMBOL", "(")
                inner = self.parse_expr()
                if not self.match("SYMBOL", ")"):
                    raise ParseError("Missing closing ')'", self.peek())
                return Rename(new_name, inner)
        if t.kind == "SYMBOL" and t.value == "(":
            self.advance()
            expr = self.parse_expr()
            if not self.match("SYMBOL", ")"):
                raise ParseError("Missing closing ')'", self.peek())
            return expr
        if self.is_ident_like(t):
            return RelRef(self.consume_ident_like())
        raise ParseError(f"Unexpected token in expression: {t.kind} {t.value!r}", t)

    def parse_attr_list(self):
        if self.peek().kind == "SYMBOL" and self.peek().value == "]":
            raise ParseError("Empty attribute list in project", self.peek())
        attrs = [self.consume_ident_like()]
        while self.match("SYMBOL", ","):
            attrs.append(self.consume_ident_like())
        return attrs

    def parse_condition(self):
        return self.parse_or_condition()

    def parse_or_condition(self):
        left = self.parse_and_condition()
        while True:
            t = self.peek()
            if t.kind == "KEYWORD" and t.value == "or":
                self.advance()
                right = self.parse_and_condition()
                left = Or(left, right)
            else:
                break
        return left

    def parse_and_condition(self):
        left = self.parse_not_condition()
        while True:
            t = self.peek()
            if t.kind == "KEYWORD" and t.value == "and":
                self.advance()
                right = self.parse_not_condition()
                left = And(left, right)
            else:
                break
        return left

    def parse_not_condition(self):
        t = self.peek()
        if t.kind == "KEYWORD" and t.value == "not":
            nxt = self.peek(1)
            if nxt.kind == "SYMBOL" and nxt.value in ("=", "!=", "<", "<=", ">", ">=", "."):
                pass  # 'not' is an operand
            else:
                self.advance()
                return Not(self.parse_not_condition())
        return self.parse_primary_condition()

    def parse_primary_condition(self):
        t = self.peek()
        if t.kind == "SYMBOL" and t.value == "(":
            self.advance()
            cond = self.parse_condition()
            self.expect("SYMBOL", ")")
            return cond
        return self.parse_comparison()

    def parse_comparison(self):
        left = self.parse_operand()
        op_token = self.peek()
        if op_token.kind == "SYMBOL" and op_token.value in ("=", "!=", "<", "<=", ">", ">="):
            op = self.advance().value
            right = self.parse_operand()
            return Comparison(op, left, right)
        raise ParseError("Expected comparison operator", op_token)

    def parse_operand(self):
        t = self.peek()
        if t.kind == "INTEGER":
            self.advance(); return Integer(t.value)
        if t.kind == "STRING":
            self.advance(); return String(t.value)
        return self.parse_attr_ref()

    def parse_attr_ref(self):
        first = self.consume_ident_like()
        if self.match("SYMBOL", "."):
            second = self.consume_ident_like()
            return AttrRef(first, second)
        return AttrRef(None, first)


# =====================================================================
# Program Parser (relation defs + query)
# =====================================================================

class ProgramParser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

    def peek(self, offset=0):
        idx = self.pos + offset
        if idx >= len(self.tokens):
            return self.tokens[-1]
        return self.tokens[idx]

    def advance(self):
        t = self.peek()
        if t.kind != "EOF":
            self.pos += 1
        return t

    def match(self, kind, value=None):
        t = self.peek()
        if t.kind == kind and (value is None or t.value == value):
            return self.advance()
        return None

    def expect(self, kind, value=None):
        t = self.peek()
        if t.kind != kind:
            raise ParseError(f"Expected {kind}, got {t.kind}", t)
        if value is not None and t.value != value:
            raise ParseError(f"Expected {value!r}, got {t.value!r}", t)
        return self.advance()

    def skip_newlines(self):
        while self.peek().kind == "NEWLINE":
            self.advance()

    def is_ident_like(self, t):
        return t.kind in ("IDENT", "KEYWORD")

    def consume_ident_like(self):
        t = self.peek()
        if self.is_ident_like(t):
            return self.advance().value
        raise ParseError(f"Expected identifier, got {t.kind}", t)

    def parse_program(self):
        relations = []
        while True:
            self.skip_newlines()
            if self.peek().kind == "EOF":
                raise ParseError("Expected query after relation definitions", self.peek())
            if not self.is_relation_def_start():
                break
            relations.append(self.parse_relation_def())

        self.skip_newlines()
        remaining = self.tokens[self.pos:]
        query = Parser(remaining).parse_query()
        return Program(relations, query)

    def is_relation_def_start(self):
        t = self.peek()
        if not self.is_ident_like(t):
            return False
        n = self.peek(1)
        return n.kind == "SYMBOL" and n.value == "("

    def parse_relation_def(self):
        name = self.consume_ident_like()
        self.expect("SYMBOL", "(")
        attrs = [self.consume_ident_like()]
        while self.match("SYMBOL", ","):
            attrs.append(self.consume_ident_like())
        self.expect("SYMBOL", ")")
        self.expect("SYMBOL", "=")
        self.expect("SYMBOL", "{")
        tuples = self.parse_tuple_list(len(attrs))
        self.expect("SYMBOL", "}")
        return RelationDef(name, attrs, tuples)

    def parse_tuple_list(self, n):
        tuples = []
        self.skip_newlines()
        if self.peek().kind == "SYMBOL" and self.peek().value == "}":
            return tuples
        while True:
            tup = self.parse_tuple(n)
            tuples.append(tup)
            if self.peek().kind == "SYMBOL" and self.peek().value == "}":
                break
            if self.peek().kind != "NEWLINE":
                raise ParseError("Expected newline or '}' after tuple", self.peek())
            self.skip_newlines()
            if self.peek().kind == "SYMBOL" and self.peek().value == "}":
                break
        return tuples

    def parse_tuple(self, n):
        values = [self.parse_tuple_value()]
        while True:
            save = self.pos
            self.skip_newlines()
            if self.peek().kind == "SYMBOL" and self.peek().value == ",":
                self.advance()
                self.skip_newlines()
                values.append(self.parse_tuple_value())
            else:
                self.pos = save
                break
        if len(values) != n:
            raise ParseError(
                f"Tuple has {len(values)} values, expected {n}", self.peek())
        return tuple(values)

    def parse_tuple_value(self):
        t = self.peek()
        if t.kind == "INTEGER":
            self.advance()
            return t.value
        if t.kind == "STRING":
            self.advance()
            return t.value
        raise ParseError(
            f"Expected tuple value, got {t.kind} {t.value!r}", t
        )


# =====================================================================
# Errors
# =====================================================================

class EvalError(Exception):
    pass

class NameError_(EvalError):
    pass

class SchemaError(EvalError):
    pass

class TypeMismatchError(EvalError):
    pass

class DuplicateAttrError(EvalError):
    pass


# =====================================================================
# Relations and evaluation
# =====================================================================

class Column:
    __slots__ = ("rel_name", "attr_name")
    def __init__(self, rel_name, attr_name):
        self.rel_name = rel_name
        self.attr_name = attr_name
    def __repr__(self):
        return f"{self.rel_name}.{self.attr_name}" if self.rel_name else self.attr_name
    def __eq__(self, other):
        return (isinstance(other, Column) and self.rel_name == other.rel_name
                and self.attr_name == other.attr_name)
    def __hash__(self):
        return hash((self.rel_name, self.attr_name))

class Relation:
    def __init__(self, name, columns, rows):
        self.name = name
        self.columns = list(columns)
        self.rows = set(rows)

    def labels(self):
        from collections import Counter
        counts = Counter(c.attr_name for c in self.columns)
        out = []
        for c in self.columns:
            if counts[c.attr_name] > 1 and c.rel_name:
                out.append(f"{c.rel_name}.{c.attr_name}")
            else:
                out.append(c.attr_name)
        return out


def resolve_attr(attr_ref, columns):
    if attr_ref.relation:
        matches = [i for i, c in enumerate(columns)
                   if c.rel_name == attr_ref.relation and c.attr_name == attr_ref.attr]
        if not matches:
            raise NameError_(f"Unknown attribute {attr_ref.relation}.{attr_ref.attr}")
        if len(matches) > 1:
            raise NameError_(f"Ambiguous attribute {attr_ref.relation}.{attr_ref.attr}")
        return matches[0]
    matches = [i for i, c in enumerate(columns) if c.attr_name == attr_ref.attr]
    if not matches:
        raise NameError_(f"Unknown attribute {attr_ref.attr}")
    if len(matches) > 1:
        raise NameError_(f"Ambiguous attribute {attr_ref.attr}")
    return matches[0]


def eval_operand(op, columns, row):
    if isinstance(op, Integer): return op.value
    if isinstance(op, String):  return op.value
    if isinstance(op, AttrRef):
        idx = resolve_attr(op, columns)
        return row[idx]
    raise EvalError(f"Unknown operand: {op}")


def eval_condition(cond, columns, row):
    if isinstance(cond, Comparison):
        lv = eval_operand(cond.left, columns, row)
        rv = eval_operand(cond.right, columns, row)
        if isinstance(lv, bool) or isinstance(rv, bool):
            pass
        lt, rt = type(lv), type(rv)
        if lt != rt:
            raise TypeMismatchError(
                f"Cannot compare {lt.__name__} with {rt.__name__}")
        op = cond.op
        if op == "=":  return lv == rv
        if op == "!=": return lv != rv
        if op == "<":  return lv < rv
        if op == "<=": return lv <= rv
        if op == ">":  return lv > rv
        if op == ">=": return lv >= rv
    if isinstance(cond, And): return eval_condition(cond.left, columns, row) and eval_condition(cond.right, columns, row)
    if isinstance(cond, Or):  return eval_condition(cond.left, columns, row) or  eval_condition(cond.right, columns, row)
    if isinstance(cond, Not): return not eval_condition(cond.cond, columns, row)
    raise EvalError(f"Unknown condition: {cond}")


# -- Operators --------------------------------------------------------

def op_select(cond, rel):
    new_rows = set()
    st = 0
    for row in rel.rows:
        st += 1
        if eval_condition(cond, rel.columns, row):
            new_rows.add(row)
    STATS["select_tuples"] += st
    return Relation(rel.name, rel.columns, new_rows)


def op_project(attrs, rel):
    indices = []
    for a in attrs:
        idx = resolve_attr(AttrRef(None, a), rel.columns)
        if idx in indices:
            raise DuplicateAttrError(f"Duplicate attribute in projection: {a}")
        indices.append(idx)

    new_columns = [rel.columns[i] for i in indices]
    new_rows = set()
    pt = 0
    for row in rel.rows:
        pt += 1
        new_rows.add(tuple(row[i] for i in indices))
    STATS["project_tuples"] += pt
    return Relation(None, new_columns, new_rows)


def op_times(left, right):
    lk = set((c.rel_name, c.attr_name) for c in left.columns)
    rk = set((c.rel_name, c.attr_name) for c in right.columns)
    collision = lk & rk
    if collision:
        raise SchemaError(
            f"Qualified name collision after times: {sorted(collision)}")
    new_columns = list(left.columns) + list(right.columns)
    new_rows = set()
    for lrow in left.rows:
        for rrow in right.rows:
            STATS["join_pairs"] += 1
            new_rows.add(lrow + rrow)
    return Relation(None, new_columns, new_rows)

def _check_equi_join_types(left, right, li, ri):
    """Raise TypeMismatchError if the two join columns hold incompatible types.

    The fast equi-join path compares values directly with ``==``.  Python
    returns False for ``1 == '1'`` instead of raising, which would silently
    violate the assignment rule that a comparison between a number and a
    string is an error.  Scanning each column once and checking that the
    combined set of value types has size at most one catches this before
    the quadratic loop starts.  The scan is linear in |left| + |right|, so
    it does not change the asymptotic cost of the join.
    """
    types = {type(row[li]) for row in left.rows}
    types |= {type(row[ri]) for row in right.rows}
    if len(types) > 1:
        names = ", ".join(sorted(t.__name__ for t in types))
        raise TypeMismatchError(
            f"Cannot compare values of different types in join: {names}"
        )
    
def _try_fast_equi_join(cond, left, right):
    if not isinstance(cond, Comparison) or cond.op != "=":
        return None
    if not (isinstance(cond.left, AttrRef) and isinstance(cond.right, AttrRef)):
        return None

    combined = list(left.columns) + list(right.columns)
    try:
        a = resolve_attr(cond.left, combined)
        b = resolve_attr(cond.right, combined)
    except NameError_:
        return None

    nl = len(left.columns)
    if a < nl and b >= nl:
        return a, b - nl
    if b < nl and a >= nl:
        return b, a - nl
    return None

def op_join(cond, left, right):
    lk = set((c.rel_name, c.attr_name) for c in left.columns)
    rk = set((c.rel_name, c.attr_name) for c in right.columns)
    collision = lk & rk
    if collision:
        raise SchemaError(
            f"Qualified name collision after join: {sorted(collision)}")

    new_columns = list(left.columns) + list(right.columns)

    # Fast path: simple equality between one left attribute and one right attribute
    fast = _try_fast_equi_join(cond, left, right)
    if fast is not None:
        li, ri = fast
        _check_equi_join_types(left, right, li, ri)
        left_rows = list(left.rows)
        right_rows = list(right.rows)
        new_rows = set()
        jp = 0

        for lrow in left_rows:
            lval = lrow[li]
            for rrow in right_rows:
                jp += 1
                if lval == rrow[ri]:
                    new_rows.add(lrow + rrow)

        STATS["join_pairs"] += jp
        return Relation(None, new_columns, new_rows)

    # Generic fallback
    left_rows = list(left.rows)
    right_rows = list(right.rows)
    new_rows = set()
    jp = 0

    for lrow in left_rows:
        for rrow in right_rows:
            jp += 1
            row = lrow + rrow
            if eval_condition(cond, new_columns, row):
                new_rows.add(row)

    STATS["join_pairs"] += jp
    return Relation(None, new_columns, new_rows)

def op_rename(new_name, rel):
    new_columns = [Column(new_name, c.attr_name) for c in rel.columns]
    return Relation(new_name, new_columns, rel.rows)

def _infer_type(rel, idx):
    for row in rel.rows:
        return type(row[idx]).__name__
    return None


def _check_union_compatible(left, right):
    if len(left.columns) != len(right.columns):
        raise SchemaError(
            f"Union incompatible: {len(left.columns)} vs {len(right.columns)} attributes")
    for lc, rc in zip(left.columns, right.columns):
        if lc.attr_name != rc.attr_name:
            raise SchemaError(
                f"Union incompatible: attribute names differ: "
                f"{lc.attr_name} vs {rc.attr_name}")
    for i in range(len(left.columns)):
        lt = _infer_type(left, i)
        rt = _infer_type(right, i)
        if lt and rt and lt != rt:
            raise SchemaError(
                f"Union incompatible: types differ at position {i}: {lt} vs {rt}")


def op_union(left, right):
    _check_union_compatible(left, right)
    return Relation(None, left.columns, left.rows | right.rows)


def op_intersect(left, right):
    _check_union_compatible(left, right)
    return Relation(None, left.columns, left.rows & right.rows)


def op_minus(left, right):
    _check_union_compatible(left, right)
    return Relation(None, left.columns, left.rows - right.rows)


# -- Evaluator --------------------------------------------------------

def eval_expr(node, db):
    if isinstance(node, RelRef):
        if node.name not in db:
            raise NameError_(f"Unknown relation {node.name}")
        return db[node.name]
    if isinstance(node, Select):
        return op_select(node.cond, eval_expr(node.input, db))
    if isinstance(node, Project):
        return op_project(node.attrs, eval_expr(node.input, db))
    if isinstance(node, Rename):
        return op_rename(node.new_name, eval_expr(node.input, db))
    if isinstance(node, Union):
        return op_union(eval_expr(node.left, db), eval_expr(node.right, db))
    if isinstance(node, Intersect):
        return op_intersect(eval_expr(node.left, db), eval_expr(node.right, db))
    if isinstance(node, Minus):
        return op_minus(eval_expr(node.left, db), eval_expr(node.right, db))
    if isinstance(node, Times):
        return op_times(eval_expr(node.left, db), eval_expr(node.right, db))
    if isinstance(node, Join):
        # Fused, but identical to times-then-select. Counts the same number of pair comparisons.
        left = eval_expr(node.left, db)
        right = eval_expr(node.right, db)
        return op_join(node.cond, left, right)
    raise EvalError(f"Unknown node type: {type(node).__name__}")


def build_db(program):
    db = {}
    for rd in program.relations:
        if len(set(rd.attrs)) != len(rd.attrs):
            raise DuplicateAttrError(
                f"Duplicate attribute names in relation {rd.name}: {rd.attrs}")
        columns = [Column(rd.name, a) for a in rd.attrs]
        rows = set(rd.tuples)
        # arity check
        for t in rows:
            if len(t) != len(rd.attrs):
                raise SchemaError(
                    f"Relation {rd.name}: tuple arity {len(t)} != {len(rd.attrs)}")
        db[rd.name] = Relation(rd.name, columns, rows)
    return db


# =====================================================================
# Tree printer
# =====================================================================

def print_tree(node, prefix="", is_last=True, is_root=True):
    if node is None:
        return
    if is_root:
        print(node.label())
    else:
        connector = "└── " if is_last else "├── "
        print(prefix + connector + node.label())
    children = node.children()
    new_prefix = "" if is_root else prefix + ("    " if is_last else "│   ")
    for i, child in enumerate(children):
        print_tree(child, new_prefix, i == len(children) - 1, False)


# =====================================================================
# Result printer
# =====================================================================

def print_relation(rel):
    labels = rel.labels()
    widths = [len(l) for l in labels]
    rows_sorted = sorted(rel.rows)
    for row in rows_sorted:
        for i, v in enumerate(row):
            widths[i] = max(widths[i], len(str(v)))
    sep = "  "
    header = sep.join(l.ljust(widths[i]) for i, l in enumerate(labels))
    line = sep.join("-" * widths[i] for i in range(len(labels)))
    print(header)
    print(line)
    for row in rows_sorted:
        print(sep.join(str(v).ljust(widths[i]) for i, v in enumerate(row)))
    print(f"({len(rows_sorted)} row{'s' if len(rows_sorted) != 1 else ''})")


# =====================================================================
# CLI
# =====================================================================

DEFAULT_PROGRAM = """
Employees (EID, Name, Age, DID) = {
  E1, John, 32, D1
  E2, Alice, 28, D2
  E3, Bob, 29, D1
}

Dept (DID, DName) = {
  D1, Sales
  D2, Eng
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


def run_program(text, mode="eval"):
    reset_stats()
    tokens = Tokenizer(text).tokenize()
    prog = ProgramParser(tokens).parse_program()
    db = build_db(prog)
    if mode == "tree":
        print_tree(prog.query)
        return
    result = eval_expr(prog.query, db)
    print_relation(result)
    print(f"join_pairs={STATS['join_pairs']} "
          f"select_tuples={STATS['select_tuples']}")


def main():
    if len(sys.argv) >= 2 and sys.argv[1] == "--tree":
        if len(sys.argv) < 3:
            print("Usage: python ra.py --tree \"<query>\"")
            return
        query = " ".join(sys.argv[2:])
        try:
            run_program(DEFAULT_PROGRAM + "\n" + query, mode="tree")
        except (LexError, ParseError) as e:
            print(f"Error: {e}")
        except EvalError as e:
            print(f"Error: {e}")
        return

    if len(sys.argv) >= 2:
        query = " ".join(sys.argv[1:])
        try:
            run_program(DEFAULT_PROGRAM + "\n" + query, mode="eval")
        except (LexError, ParseError) as e:
            print(f"Error: {e}")
        except EvalError as e:
            print(f"Error: {e}")
        return

    # No args: run cases 18-25
    cases = [
        ("18", "select[A=B](R)"),
        ("19", "Employees join[Employees.DID=Dept.DID] Dept"),
        ("20", "rename[E2](Employees) join[Employees.DID=E2.DID] Employees"),
        ("21", "Employees union R"),
        ("22", "select[Age>'30'](Employees)"),
        ("23", "project[DID](Employees)"),
        ("24", "project[Name, Name](Employees)"),
        ("25", "select[Age>100](Employees)"),
    ]
    for num, q in cases:
        print(f"\n--- Case {num}: {q}")
        try:
            run_program(DEFAULT_PROGRAM + "\n" + q, mode="eval")
        except (LexError, ParseError) as e:
            print(f"Error: {e}")
        except EvalError as e:
            print(f"Error: {e}")


if __name__ == "__main__":
    main()