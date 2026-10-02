"""S4a: adding a second parent may not reorder an inherited check sequence."""
import unittest
from scir import parse_document
from scir.refinement import Checker, compile_profile


class ParentOrderTests(unittest.TestCase):
    def test_conflicting_parent_orders_are_rejected(self):
        source = parse_document('validation(P, stage(a,parents,rules(x,y)), '
                                'stage(b,parents,rules(y,x)), stage(c,parents(a,b),rules))')
        with self.assertRaises(ValueError):
            compile_profile(source, 'P', {'x': Checker(lambda d: ()), 'y': Checker(lambda d: ())})
