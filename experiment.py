#!/usr/bin/env python3
"""experiment.py -- Section 8.3.

Runs R join[R.b=S.b] S at n = 1000, 2000, ..., 64000 tuples per relation
and writes the table required by the report.  Also runs a select and a
project at the same sizes for question 3.

Usage:
    python experiment.py --match-rate 10 --out results.csv
"""
import argparse
import csv
import sys
import time

import datagen
from ra import (
    Tokenizer, Parser, eval_expr,
    STATS, reset_stats,
    Relation, Column,
)

SIZES = [1000, 2000, 4000, 8000, 16000, 32000, 64000]
JOIN_QUERY    = "R join[R.b=S.b] S"
SELECT_QUERY  = "select[b>0](R)"          # drops only tuples with b == 0
PROJECT_QUERY = "project[b](R)"           # ~ n / match_rate rows


def make_db(n, m, match_rate, seed):
    """Generate R(a,b) and S(b,c) and return a database dict of Relations."""
    R, S, d = datagen.generate(n, m, match_rate, seed)
    db = {}
    db["R"] = Relation("R", [Column("R", "a"), Column("R", "b")], set(R))
    db["S"] = Relation("S", [Column("S", "b"), Column("S", "c")], set(S))
    return db


def parse_query(query_str):
    """Tokenize and parse a query string into an AST."""
    tokens = Tokenizer(query_str).tokenize()
    return Parser(tokens).parse_query()


def run_one(db, query_ast, query_str, n, m):
    """Evaluate one query against the given database, returning a result row."""
    reset_stats()
    t0 = time.perf_counter()
    result = eval_expr(query_ast, db)
    t1 = time.perf_counter()

    return {
        "n": n,
        "m": m,
        "query": query_str,
        "join_pairs":     STATS["join_pairs"],
        "select_tuples":  STATS["select_tuples"],
        "project_tuples": STATS["project_tuples"],
        "wall_time": t1 - t0,
        "output": len(result.rows),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--match-rate", type=int, default=10)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--sizes", type=int, nargs="*", default=SIZES)
    ap.add_argument("--queries", nargs="*", default=["join", "select", "project"])
    ap.add_argument("--out", default="results.csv")
    args = ap.parse_args()

    # Parse all queries once
    query_map = {
        "join":    JOIN_QUERY,
        "select":  SELECT_QUERY,
        "project": PROJECT_QUERY,
    }
    parsed_queries = {
        name: parse_query(qstr)
        for name, qstr in query_map.items()
    }

    rows = []
    print(f"{'query':>8} {'n':>7} {'m':>7} {'pairs':>14} "
          f"{'sel':>10} {'proj':>10} {'wall (s)':>10} {'out':>9}")

    for n in args.sizes:
        db = make_db(n, n, args.match_rate, args.seed)

        for qname in args.queries:
            qstr = query_map[qname]
            qast = parsed_queries[qname]

            r = run_one(db, qast, qstr, n, n)
            rows.append(r)

            print(f"{qname:>8} {r['n']:>7} {r['m']:>7} "
                  f"{r['join_pairs']:>14} {r['select_tuples']:>10} "
                  f"{r['project_tuples']:>10} {r['wall_time']:>10.3f} "
                  f"{r['output']:>9}")
            sys.stdout.flush()

    with open(args.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()