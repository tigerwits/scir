"""Compile the explicit law model and reject unapproved proof assumptions."""
from pathlib import Path
import re
import subprocess
import sys


def main():
    if len(sys.argv) != 2:
        raise SystemExit('usage: check_lean_model.py /path/to/pinned/lean')
    root = Path(__file__).resolve().parents[1]
    model = root/'proofs'/'ProfileLaws.lean'
    text = model.read_text(encoding='utf-8')
    if re.search(r'\b(sorry|admit|axiom|unsafe)\b', text):
        raise ValueError('model contains an admission or unsafe declaration')
    version = subprocess.check_output([sys.argv[1], '--version'], text=True)
    print(version, end='')
    if 'version 4.19.0' not in version:
        raise ValueError('expected the explicitly pinned Lean 4.19.0 toolchain')
    result = subprocess.run([sys.argv[1], '-DwarningAsError=true', str(model)], capture_output=True, text=True)
    print(result.stdout, end='')
    print(result.stderr, end='', file=sys.stderr)
    if result.returncode:
        raise SystemExit(result.returncode)
    expected = ('extensive', 'monotone', 'least_closed', 'idempotent', 'tuple_injective',
                'reference_injective', 'text_reference_distinct', 'argument_arity_distinct', 'named_role_distinct')
    if any(f"'SCIR.{name}'" not in result.stdout for name in expected) or 'sorryAx' in result.stdout:
        raise ValueError('missing theorem assumption report or admitted proof')
    for group in re.findall(r'depends on axioms:\s*\[(.*?)\]', result.stdout, re.S):
        names = {name.strip() for name in group.split(',') if name.strip()}
        if not names <= {'propext', 'Classical.choice', 'Quot.sound'}:
            raise ValueError('unexpected theorem assumptions: '+repr(names))
    print('LEAN_MODEL_CHECKED=9; scope=abstract-closure-and-specific-tree-distinction-laws')


if __name__ == '__main__':
    main()
