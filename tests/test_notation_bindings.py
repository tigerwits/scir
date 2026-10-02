import unittest
from unittest.mock import patch
from scir import parse_document, digest
from scir import profile as p
from scir.notation import lower, pretty, Limits


class NotationBindingTests(unittest.TestCase):
    def test_alias_definition_site_and_literal_exclusions(self):
        source = '''@using K = Original
@let x = K.f(a)
@using Original = Later
hold($x, K, "K.f", &K.f, K.key: t"K.f")'''
        expected = parse_document('hold("Original.f"(a), K, "K.f", "scir.ref"("K.f"), "scir.kw"("K.key"("scir.text"("K.f"))))')
        self.assertEqual(lower(source), expected)
        self.assertEqual(lower('@using A = B\n@using B = C\nA.f(x)'), parse_document('"B.f"(x)'))
        self.assertEqual(lower('@using K = A\n@using L = K.sub\nL.f(x)'), parse_document('"A.sub.f"(x)'))

    def test_values_are_single_objects_with_separate_occurrences(self):
        source = '@let pair = (a,b)\nf($pair)\nf($pair)'
        expected = parse_document('f("scir.tuple"(a,b))\nf("scir.tuple"(a,b))')
        self.assertEqual(lower(source), expected)
        self.assertEqual(lower(pretty(expected)), expected)
        self.assertEqual(lower('@let unused = t"kept only in source"'), ())
        self.assertEqual(lower('@using x = A\n@let x = a\nx.f($x)'), parse_document('"A.f"(a)'))

    def test_undefined_duplicate_callable_and_nested_declarations_fail(self):
        cases = ('$x', '@let x = $x', '@let x = $y\n@let y = a',
                 '@let x = a\n@let x = b', '@using K=A\n@using K=B',
                 '@let x = f\n$x(a)', 'f(@let x=a)', '@import x',
                 '@using K = "not a namespace"', '@let a.b = x', '@let f(x)=x')
        for source in cases:
            with self.subTest(source=source), self.assertRaises(ValueError):
                lower(source)
        lower('@let x = a')
        with self.assertRaises(ValueError):
            lower('$x')

    def test_alpha_renaming_preserves_lowered_content(self):
        for n in range(1, 50):
            def source(alias, local):
                return f'@using {alias} = Project.deep\n@let {local} = (a, role: t"exact")\n' + '\n'.join(f'{alias}.record($'+local+')' for _ in range(n))
            self.assertEqual(digest(lower(source('K', 'x'))), digest(lower(source('Other', 'value'))))

    def test_expansion_and_declaration_limits_precede_serialization(self):
        source = '@let v0 = a\n' + '\n'.join(f'@let v{i} = pair($v{i-1},$v{i-1})' for i in range(1, 20)) + '\n$v19'
        with patch('scir.notation.format_document', side_effect=AssertionError('must not serialize')):
            with self.assertRaises(p.LimitError):
                lower(source)
        with self.assertRaises(p.LimitError):
            lower('@let x=a\n@let y=b', limits=Limits(declarations=1))
        with self.assertRaises(p.LimitError):
            lower('@let x=t"'+('a'*100)+'"\nf($x,$x)', limits=Limits(expanded_bytes=150))
        with self.assertRaises(p.LimitError):
            lower('@let x=(a,b)\n$x\n$x', limits=Limits(nodes=5))
