In summary, 3 working sessions of many hours each. There were many more issues with the AI generated code than written here.
### 9/16 — First draft of EBNF and tuple-list handling

Trying to write the EBNF before writing the parser, covering relation definitions, tuple lists, newlines, and comments.

Tried: started from the Wikipedia EBNF article and had AI draft a grammar. The first version used `TupleList ::= Tuple { Newline Tuple } [ Newline ]` and `Tuple ::= TupleValue { "," TupleValue }`. The parser algorithm also parsed the first tuple immediately without skipping leading newlines.

What broke: relation definitions with a blank line after `{` or before `}` failed, and trailing newlines were not handled cleanly. The grammar required the first token of a tuple list to be a `Tuple`, but the tokenizer emits `NEWLINE` tokens. I found this by manually tracing `R (x) = {\n 1\n 2\n}` and by testing an empty tuple list and a tuple list with leading blank lines.

AI issue: AI produced a grammar that looked reasonable but did not match its own parser algorithm. Fix: changed `TupleList` to allow optional leading `Newline+` and trailing `Newline+`, and made the parser skip newlines before parsing the first tuple. Also documented the bounded-backtracking rule for newlines before commas.

### 9/18 — Tokenizer, parser cases, and instrumentation

Trying to get the hand-written tokenizer and recursive-descent parser through the required tokenizer and grammar cases, then add the Section 8.2 counters.

Tried: AI suggested checking parentheses by splitting on them before tokenizing. It also suggested incrementing `STATS["select_tuples"] += 1` directly inside the row loop in `op_select`. I implemented maximal munch for `>=`, `<=`, `!=`, and `-30`, and kept string literals entirely inside the tokenizer.

What broke: pre-tokenizing parenthesis matching fails case 5, `select[Name='Bob)'](R)`, because the `)` is inside a string. The per-row stats increment added overhead and made the counter code noisy. Also, the first `experiment.py` rebuilt and reparsed the entire relation program for every query and every `n`, so the early timings were dominated by setup rather than query execution.

AI issue: AI’s first tokenizer/parser suggestion was incomplete for quoted strings and keyword-as-identifier cases. I found it by running the Section 7 cases 1–9 and 10–17. Fix: strings are consumed by the tokenizer, `not`, `select`, `project`, and `rename` use one-token lookahead, and stats are accumulated in local counters and added once per operator. Later, `experiment.py` was changed to build `R` and `S` directly as `Relation` objects once per `n` and to parse query strings once at startup.

### 9/28 — Performance study and join hot loop

Trying to run the Section 8.3 experiment at 1k–64k and answer the report questions.

Tried: first used an AI-assisted `experiment.py` that rebuilt and reparsed the database for every query and size. After fixing that, I ran the nested-loop join. AI also suggested adding a per-pair type check inside the fast equi-join loop to catch `TypeMismatchError`.

What broke: the original experiment produced wall times dominated by parsing and database setup. After fixing that, the join times showed the expected quadratic trend. The per-pair type check made the hot loop slower and cluttered the innermost loop. For the equality fast path, the check is unnecessary for the generated integer/integer data; the generic condition evaluator still performs type checks for non-fast-path joins and selects. I found this by comparing before/after timings and by checking that the comparison counter still matched `n*m` while wall time rose.

AI issue: AI’s first performance script was slow and incomplete because it re-did parsing and database construction inside the timed function. It also put type validation in the innermost join loop. Fix: build the database once per `n`, reuse parsed query ASTs, and keep only `jp += 1` plus the equality test in the hot loop.

The two join timing tables below show the effect of removing the repeated parsing/database construction before the later hot-loop cleanup.

**(Join)**
**Before:**

| n     | m     | comparisons | wall time (s) | output tuples |
|-------|-------|-------------|---------------|---------------|
| 1000  | 1000  | 1,000,000   | 1.166         | 10,169        |
| 2000  | 2000  | 4,000,000   | 4.783         | 19,756        |
| 4000  | 4000  | 16,000,000  | 18.590        | 39,977        |
| 8000  | 8000  | 64,000,000  | 76.844        | 79,669        |
| 16000 | 16000 | 256,000,000 | 324.790       | 159,823       |
| 32000 | 32000 | 1,024,000,000 | 1346.656    | 319,454       |
| 64000 | 64000 | 4,096,000,000 | 5356.260    | 640,388       |

**After**

| n     | m     | comparisons   | wall time (s) | output tuples |
|-------|-------|---------------|---------------|---------------|
| 1000  | 1000  | 1,000,000     | 0.034         | 10,169        |
| 2000  | 2000  | 4,000,000     | 0.120         | 19,756        |
| 4000  | 4000  | 16,000,000    | 0.502         | 39,977        |
| 8000  | 8000  | 64,000,000    | 1.972         | 79,669        |
| 16000 | 16000 | 256,000,000   | 10.554        | 159,823       |
| 32000 | 32000 | 1,024,000,000 | 45.751        | 319,454       |
| 64000 | 64000 | 4,096,000,000 | 213.158       | 640,388       |