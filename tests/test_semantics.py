"""Semantic tests -- assignment cases 18 to 25."""
import unittest

from test_helpers import (
    build_test_db, eval_query,
    SchemaError, TypeMismatchError, DuplicateAttrError, NameError_,
)


class TestSemantics(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.db = build_test_db()

    # ------------------------------------------------------------------
    # Case 18: select[A=B](R) compares two attributes.
    # ------------------------------------------------------------------
    def test_case_18_attribute_vs_attribute(self):
        result = eval_query("select[A=B](R)", self.db)
        # R = {(1,1), (2,2), (3,1)}; A=B keeps (1,1) and (2,2).
        self.assertEqual(result.rows, {(1, 1), (2, 2)})

    # ------------------------------------------------------------------
    # Case 19: qualified names resolve, both DID columns kept.
    # ------------------------------------------------------------------
    def test_case_19_qualified_join(self):
        result = eval_query("Emp join[Emp.DID=Dept.DID] Dept", self.db)
        # Emp has 3 rows, all with DID in {D1, D2, D1};
        # Dept has D1 and D2 -> all three Emp rows match.
        self.assertEqual(len(result.rows), 3)
        labels = result.labels()
        # Both DID columns must be distinguishable in the schema.
        self.assertIn("Emp.DID", labels)
        self.assertIn("Dept.DID", labels)

    # ------------------------------------------------------------------
    # Case 20: self join via rename.
    # ------------------------------------------------------------------
    def test_case_20_self_join_with_rename(self):
        result = eval_query(
            "rename[E2](Emp) join[Emp.MgrID=E2.EID] Emp", self.db
        )
        # Every Emp row has MgrID=E1; there is exactly one E1 in Emp.
        self.assertEqual(len(result.rows), 3)

    def test_case_20b_self_join_without_rename_fails(self):
        # Without rename, the qualified names collide -> SchemaError.
        with self.assertRaises(SchemaError):
            eval_query("Emp join[Emp.MgrID=Emp.EID] Emp", self.db)

    # ------------------------------------------------------------------
    # Case 21: union with different schemas is a schema error.
    # ------------------------------------------------------------------
    def test_case_21_union_incompatible(self):
        with self.assertRaises(SchemaError):
            eval_query("Employees union R", self.db)

    # ------------------------------------------------------------------
    # Case 22: comparing a number to a string is a type error.
    # ------------------------------------------------------------------
    def test_case_22_type_mismatch(self):
        with self.assertRaises(TypeMismatchError):
            eval_query("select[Age>'30'](Employees)", self.db)

    # ------------------------------------------------------------------
    # Case 23: projection removes duplicates.
    # ------------------------------------------------------------------
    def test_case_23_projection_dedup(self):
        result = eval_query("project[DID](Employees)", self.db)
        # Employees has DID values D1, D2, D1 -> two distinct tuples.
        self.assertEqual(len(result.rows), 2)
        self.assertEqual(result.rows, {('D1',), ('D2',)})

    # ------------------------------------------------------------------
    # Case 24: duplicate attribute in projection -- documented rule.
    # ------------------------------------------------------------------
    def test_case_24_duplicate_projection_error(self):
        with self.assertRaises(DuplicateAttrError):
            eval_query("project[Name, Name](Employees)", self.db)

    # ------------------------------------------------------------------
    # Case 25: empty result still prints a schema cleanly.
    # ------------------------------------------------------------------
    def test_case_25_empty_result(self):
        result = eval_query("select[Age>100](Employees)", self.db)
        self.assertEqual(len(result.rows), 0)
        # Schema is preserved.
        self.assertEqual(len(result.columns), 4)
        labels = result.labels()
        self.assertEqual(labels, ['EID', 'Name', 'Age', 'DID'])

    # ------------------------------------------------------------------
    # Extra: unknown relation is a name error.
    # ------------------------------------------------------------------
    def test_extra_unknown_relation(self):
        with self.assertRaises(NameError_):
            eval_query("Unknown", self.db)

    # ------------------------------------------------------------------
    # Extra: unknown attribute is a name error.
    # ------------------------------------------------------------------
    def test_extra_unknown_attribute(self):
        with self.assertRaises(NameError_):
            eval_query("select[Nope=1](Employees)", self.db)

    # ------------------------------------------------------------------
    # Extra: select with a qualified attribute on one side only.
    # ------------------------------------------------------------------
    def test_extra_qualified_select(self):
        result = eval_query("select[Emp.DID='D1'](Emp)", self.db)
        self.assertEqual(len(result.rows), 2)

    # ------------------------------------------------------------------
    # Extra: intersect and minus are set operations on the left schema.
    # ------------------------------------------------------------------
    def test_extra_intersect_and_minus(self):
        db = self.db
        # R and S are not union-compatible (R has A,B; S has B,C),
        # so use matching single-attribute relations A and B.
        inter = eval_query("A intersect B", db)
        self.assertEqual(inter.rows, {(2,)})
        diff = eval_query("A minus B", db)
        self.assertEqual(diff.rows, {(1,)})

    # ------------------------------------------------------------------
    # Extra: rename does not copy data; columns get the new name.
    # ------------------------------------------------------------------
    def test_extra_rename_columns(self):
        result = eval_query("rename[X](Employees)", self.db)
        self.assertEqual(result.name, 'X')
        for c in result.columns:
            self.assertEqual(c.rel_name, 'X')
        self.assertEqual(len(result.rows), 3)

    # ------------------------------------------------------------------
    # Extra: project result has no relation name.
    # ------------------------------------------------------------------
    def test_extra_project_schema(self):
        result = eval_query("project[Name](Employees)", self.db)
        self.assertIsNone(result.name)
        self.assertEqual(len(result.columns), 1)
        self.assertEqual(result.columns[0].attr_name, 'Name')


if __name__ == '__main__':
    unittest.main()