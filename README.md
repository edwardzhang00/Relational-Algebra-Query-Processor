## Relational Algebra Engine

A relational algebra engine implementing a tokenizer, recursive descent parser, parse tree printer, and evaluator for the six core relational algebra operators. Requires Python 3.11 or later.

## Running a Query
```
# Evaluate a query
python ra.py "project[Name](select[Age>30](Employees))"

# Print the parse tree without executing
python ra.py --tree "project[Name](select[Age>30](Employees))"

# Run all semantic test cases (18-25)
python ra.py
```

### Loading Your Own Data

To run queries against your own relations, create a file with relation definitions followed by a query, then pipe it through the engine. You can also modify `DEFAULT_PROGRAM` in `ra.py`

### Running the Performance Study

```
# Generate data and run the full experiment
python experiment.py --match-rate 10 --out results.csv

# Run a subset of sizes
python experiment.py --sizes 1000 2000 4000

# Run only the join query
python experiment.py --queries join
```

### Generating Test Data

```
python datagen.py --n 10000 --m 10000 --match-rate 10 --out data/prog_10000.txt
```

### Relation Definitions

```
RelationName (Attr1, Attr2, ...) = {
  value1, value2, ...
  value1, value2, ...
}
```

- Values are numbers or strings.
- Strings with commas, spaces, parentheses, or quotes must be single-quoted.
- Two single quotes inside a quoted string represent one literal quote.
- Duplicate tuples collapse to one (set semantics).
- Lines starting with `//` are comments.

### Operators

|Operator|Syntax|Description|
|---|---|---|
|Select|`select[condition](expr)`|Filters tuples by condition|
|Project|`project[attr1, attr2](expr)`|Selects attributes, removes duplicates|
|Rename|`rename[newName](expr)`|Renames the relation|
|Union|`expr union expr`|Set union (requires union compatibility)|
|Intersect|`expr intersect expr`|Set intersection|
|Minus|`expr minus expr`|Set difference|
|Times|`expr times expr`|Cartesian product|
|Join|`expr join[condition] expr`|Theta join (times + select)|

### Conditions

Conditions support comparisons (`=`, `!=`, `<`, `<=`, `>`, `>=`) combined with `and`, `or`, `not`, and parentheses. Operands can be numbers, strings, or attribute names (optionally qualified as `Relation.Attribute`).

### Precedence (highest to lowest)

1. Unary operators (`select`, `project`, `rename`, parentheses)
2. `times`, `join`
3. `intersect`
4. `union`, `minus`

All binary operators are left-associative.

### Condition Precedence (highest to lowest)

1. Comparisons (non-associative)
2. `not` (right-associative)
3. `and` (left-associative)
4. `or` (left-associative)

## Error Handling

The engine reports five categories of errors with position information where applicable:

- **Lexical errors**: Unterminated strings, invalid characters, malformed numbers
- **Syntax errors**: Missing parentheses, empty projection lists, missing operands
- **Name errors**: Unknown relations or attributes, ambiguous attribute references
- **Schema errors**: Union incompatibility, qualified name collisions
- **Type errors**: Comparing numbers to strings

All errors produce a clear message; no stack traces are shown.

## Known Limitations and Documented Decisions

### Self-Joins and Why `rename` Is Necessary

Consider the self-join:`rename[E2](Emp) join[Emp.MgrID=E2.EID] Emp`. Without `rename`, the only way to write this is: `Emp join[Emp.MgrID=Emp.EID] Emp`

This query is unanswerable in our algebra for two reasons.

1. **Qualified-name collision in the schema.**  
`join` is defined as `times` followed by `select`. The `times` operator concatenates the attributes of both inputs, qualified by relation name. If both inputs are named `Emp`, thecombined schema contains duplicate qualified columns such as `Emp.EID` and `Emp.EID`, `Emp.MgrID` and `Emp.MgrID`. Our `op_join` raises a schema error on any qualified-name collision. Even if duplicates were allowed, `Emp.EID` would not identify which copy of `Emp` is meant.

2. **Ambiguous attribute references in the condition.**  
The join condition `Emp.MgrID = Emp.EID` is ambiguous. The resolver finds multiple columns matching `Emp.EID` and raises `Ambiguous attribute Emp.EID`. It cannot know whether `Emp.MgrID` should compare to the right-hand `Emp.EID` or to its own `Emp.EID`.

`rename[E2](Emp)` solves both problems by giving one copy of `Emp` a distinct relation name. The left side then has columns like `E2.EID` and `E2.MgrID`, while the right side still has `Emp.EID` and `Emp.MgrID`. The condition `Emp.MgrID = E2.EID` is now unambiguous: the employee’s manager ID equals the manager copy’s employee ID. So `rename` is not syntactic sugar here. It is the only way to make the two copies of `Emp` distinguishable.

### Duplicate Attributes in Projection

`project[Name, Name](R)` is rejected with a clear error. The assignment left this as a design decision; we chose to reject it rather than silently deduplicate.

### Keyword as Identifier

Keywords (`select`, `project`, etc.) may be used as attribute or relation names when the grammar position expects an identifier. For example, `select[union=3](R)` treats `union` as an attribute name. This is resolved by one token of lookahead.

### Qualified Name Collisions

After `times` or `join`, if both inputs contain an attribute with the same qualified name (relation name + attribute name), that is a schema error. This is why `rename` is required for self-joins.

### Union Compatibility

Two relations are union-compatible if they have the same number of attributes, the same attribute names in the same order, and compatible types position by position. Otherwise, `union`, `intersect`, and `minus` raise a schema error.

### Type Comparisons

Comparing a number to a string is a type error, not a silent `false`.

### Integer Literals

Integer literals are signed 64-bit values. Leading zeros are allowed (`007` is 7). There is no unary minus; the minus sign is part of the literal.

### String Literals

Strings are single-quoted. Two consecutive single quotes inside a string represent one literal quote. There are no backslash escapes. Strings may span multiple lines.

### Bare Values in Tuple Definitions

Inside a relation definition tuple, a bare token that is not a valid integer is treated as a string. Bare strings may contain any character except commas, whitespace, parentheses, braces, single quotes, or `//`.

## File Structure

```
.
├── .gitignore
├── ra.py
├── datagen.py
├── experiment.py
├── GRAMMAR.md
├── REPORT.md
├── DESIGN_LOG.md
├── README.md
├── images/
│   ├── join_loglog.png
│   ├── join_linear.png
│   ├── select_linear.png
│   └── project_linear.png
└── tests/
    ├── test_helpers.py
    ├── test_tokenizer.py
    ├── test_parser.py
    ├── test_semantics.py
    └── run_tests.py
```

## Running the Tests

The test suite covers all 25 required cases from the assignment:

`python tests/run_tests.py`

Or run individual test categories:

```
python tests/test_tokenizer.py   # Cases 1-9
python tests/test_parser.py      # Cases 10-17
python tests/test_semantics.py   # Cases 18-25
```

#### Notes on Tests
The prefixed `test_extra_` tests in each file catch regressions the 25 required cases miss.

`test_case_20b_self_join_without_rename_fails` is the assertion that backs the README explanation you asked about: without `rename`, the qualified name `Emp.EID` collides with itself and the engine raises a `SchemaError` rather than producing a wrong answer.