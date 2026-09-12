"""Smoke-check the reproducible research scripts as well as the library."""
import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]


def load(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/'tools'/f'{name}.py')
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ResearchTests(unittest.TestCase):
    def test_corpus_script(self):
        report=load('study_corpus').run()
        self.assertEqual(report['fixtures'],17)
        self.assertEqual(report['candidate_documents'],19)
        self.assertEqual(report['status'],'structural checks passed')

    def test_seeded_property_script(self):
        report=load('check_properties').run(seed=88,cases=50)
        self.assertEqual(report['documents'],50)
        self.assertEqual(report['status'],'passed')


if __name__=='__main__': unittest.main()
