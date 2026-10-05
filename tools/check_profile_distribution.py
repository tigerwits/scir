"""Build/install smoke checks outside the checkout; no runtime test dependencies."""
from pathlib import Path, PurePosixPath
import json
import os
import subprocess
import sys
import tarfile
import tempfile
import zipfile


def run(*args, **kwargs):
    subprocess.run([sys.executable, '-m', 'pip', *args], check=True, **kwargs)


def package_bytes(wheel):
    with zipfile.ZipFile(wheel) as archive:
        return {name: archive.read(name) for name in archive.namelist() if name.startswith('scir/')}


def unpack_source(archive, destination):
    """Extract bounded regular source files without accepting archive links."""
    roots, count, total = set(), 0, 0
    with tarfile.open(archive) as package:
        for member in package:
            path = PurePosixPath(member.name)
            if path.is_absolute() or any(p in ("", ".", "..") for p in path.parts) or "\\" in member.name or ":" in member.name:
                raise ValueError("unsafe source archive path")
            roots.add(path.parts[0])
            if member.isdir():
                continue
            count += 1
            total += member.size
            if not member.isfile() or count > 10000 or total > 32_000_000:
                raise ValueError("source archive must contain bounded regular files")
            target = destination.joinpath(*path.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            with package.extractfile(member) as source:
                target.write_bytes(source.read())
    if len(roots) != 1:
        raise ValueError("source archive must have one project root")
    return destination / roots.pop()


def main():
    root = Path(__file__).resolve().parents[1]
    wheels, archives = list((root/'dist').glob('*.whl')), list((root/'dist').glob('*.tar.gz'))
    if len(wheels) != 1 or len(archives) != 1:
        raise ValueError('build exactly one wheel and one source distribution first')
    required = {'profile.py', 'knowledge.py', 'changes.py', 'notation.py', '_profile_cli.py', 'diagnostics.py', 'delivery.py', 'dialects.py', 'dialect_rules.py'}
    content = package_bytes(wheels[0])
    assert all('scir/'+name in content for name in required)
    with tarfile.open(archives[0]) as archive:
        names = {name.partition('/')[2] for name in archive.getnames() if '/' in name}
        assert '.github/maintenance/prune_merged_branches.py' in names
        assert {name for name in names if name.lower().endswith(('.md', '.markdown', '.mdx'))} == {'README.md', 'AGENTS.md'}
        assert {'proofs/ProfileLaws.lean', 'proofs/lean-toolchain', 'docs/guides.scir',
                'examples/working-profile/notes.scix', 'tools/study_profiles.py',
                'examples/consumer-lifecycle/policy.py', 'examples/consumer-lifecycle/notes.scir',
                'spec/workflows.scir', 'tools/study_delivery.py',
                'spec/profiles.scir', 'spec/index.scir', 'tools/check_dialects.py',
                'examples/consumer-lifecycle/dialect.py', 'examples/consumer-lifecycle/dialect_run.py'} <= names
    with tempfile.TemporaryDirectory() as temp:
        workspace = Path(temp)
        source_project = unpack_source(archives[0], workspace / 'source')
        rebuilt = workspace/'rebuilt'
        rebuilt.mkdir()
        run('wheel', '--no-deps', str(archives[0]), '--wheel-dir', str(rebuilt), cwd=workspace)
        rebuilt_wheel, = rebuilt.glob('*.whl')
        assert package_bytes(rebuilt_wheel) == content
        for number, wheel in enumerate((wheels[0], rebuilt_wheel)):
            site = workspace/f'site{number}'
            run('install', '--no-deps', '--target', str(site), str(wheel), cwd=workspace)
            env = dict(os.environ, PYTHONPATH=str(site), PYTHONDONTWRITEBYTECODE='1')
            # The sdist owns a complete SCIR collection, not only a buildable wheel.
            subprocess.run([sys.executable, str(source_project / 'spec/check.py')], cwd=workspace, env=env, check=True)
            for skill in ('scir', 'scir-migrate'):
                subprocess.run([sys.executable, str(source_project / 'spec/check.py'), 'export', '--skill', skill,
                                '--out', str(workspace / f'{number}-{skill}')], cwd=workspace, env=env,
                               check=True, stdout=subprocess.DEVNULL)
            smoke = '''import json, pathlib, scir
from scir.notation import lower
from scir.knowledge import build_index, select
from scir.changes import propose
from scir.diagnostics import diagnose
from scir.delivery import selection
from scir.dialects import Context, Dialect, from_constraint, evaluate
from scir.dialect_rules import working
assert pathlib.Path(scir.__file__).resolve().is_relative_to(pathlib.Path(__import__('sys').argv[1]).resolve())
assert scir.FORMAT_VERSION == "1.0"
dialect = Dialect("installed", "1", (from_constraint("working", "1", "a"*64, working),))
receipt = evaluate((), dialect, Context("fixture", "1"), collection="installed")
assert receipt.conforms and receipt.matches((), dialect, Context("fixture", "1"), collection="installed")
doc = lower('record(A, Note, t"literal")')
index = build_index(doc, collection="installed")
assert select(index, ("A",)).document == doc
request = json.dumps({"version":"scir-change/1", "collection":"installed", "expected_snapshot":index.snapshot, "operations":[]})
assert propose(index, request).document == doc
assert diagnose(index, ("A",))["selected"]["records"] == 1
delivery = selection(index, ("A",), encoding="notation")
assert delivery.checked_artifact(json.loads(delivery.packet)["artifact"]["sha256"]) == delivery.artifact
print(json.dumps({"package":scir.__version__,"installed_from":scir.__file__,"checked":True}))
'''
            subprocess.run([sys.executable, '-c', smoke, str(site)], cwd=workspace, env=env, check=True)
            subprocess.run([sys.executable, '-m', 'scir', 'lower', '--operators', 'arithmetic/1'],
                           input=b'a+b', cwd=workspace, env=env, check=True)
    print(json.dumps({'wheel': 'pass', 'rebuilt_sdist': 'pass', 'outside_checkout': True}))


if __name__ == '__main__':
    main()
