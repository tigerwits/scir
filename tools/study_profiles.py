"""Information-matched profile payloads and complete workflow envelopes.

Synthetic structural/size evaluation only. No model calls or search-quality claim.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import sys
from scir import Term, __version__, FORMAT_VERSION, parse_document, format_document, digest
from scir import profile as p
from scir.notation import lower, pretty, environment_digest
from scir.knowledge import build_index, select
from scir.changes import propose


def fixture():
    source = '''@using C = Communication
@let total = a + b
record(A1, Assumption, idempotent(handler), status: unverified)
record(D1, Decision, use(outbox), dependsOn: (&A1,), reason: t"Keep writes and delivery separate.", status: proposed)
record(G1, Requirement, environment(staging))
record(T1, Task, C.send(doc, from: alice, to: bob, amount: $total), dependsOn: (&D1,), scope: (&G1,), status: blocked)
'''
    expected = parse_document('''record(A1, Assumption, idempotent(handler), "scir.kw"(status(unverified)))
record(D1, Decision, use(outbox), "scir.kw"(dependsOn("scir.tuple"("scir.ref"(A1))), reason("scir.text"("Keep writes and delivery separate.")), status(proposed)))
record(G1, Requirement, environment(staging))
record(T1, Task, "Communication.send"(doc, "scir.kw"(amount(plus(a, b)), from(alice), to(bob))), "scir.kw"(dependsOn("scir.tuple"("scir.ref"(D1))), scope("scir.tuple"("scir.ref"(G1))), status(blocked)))
''')
    for number in range(16):
        payload = f'Independent note {number}: preserve uncertainty, source scope and exact literal text; do not infer an action from its mention.'
        source += f'record(N{number}, Note, t{json.dumps(payload)})\n'
        expected += (Term('record', (Term(f'N{number}'), Term('Note'), Term(p.TEXT, (Term(payload),)))),)
    return source, expected


def encode_json(term):
    return [term.symbol, [encode_json(t) for t in term.args]]


def decode_json(value):
    if type(value) is not list or len(value) != 2 or type(value[0]) is not str or type(value[1]) is not list:
        raise ValueError('invalid JSON tree')
    return Term(value[0], tuple(decode_json(v) for v in value[1]))


def evaluate(tokens=False):
    encodings = {}
    tokenizer = {'status': 'unmeasured'}
    if tokens:
        import tiktoken
        version = importlib.metadata.version('tiktoken')
        if version != '0.12.0':
            raise ValueError('this protocol pins tiktoken 0.12.0')
        encodings = {name: tiktoken.get_encoding(name) for name in ('o200k_base', 'cl100k_base')}
        tokenizer = {'status': 'measured', 'version': version, 'encodings': list(encodings),
                     'model_mapping': None}
    def cost(value):
        return {'bytes': len(value.encode('utf-8')),
                **{name: len(encoding.encode(value, disallowed_special=())) for name, encoding in encodings.items()}}
    source, expected = fixture()
    assert lower(source, operators='arithmetic/1') == expected
    native, explicit = format_document(expected), pretty(expected)
    wire = json.dumps([encode_json(t) for t in expected], ensure_ascii=False, separators=(',', ':')) + '\n'
    assert tuple(decode_json(t) for t in json.loads(wire)) == expected
    assert parse_document(native) == expected and lower(explicit) == expected
    payloads = {'native.scir': native, 'compact-tree.json': wire,
                'explicit.scix': explicit, 'authored.scix': source}
    guides = {
        'native.scir': 'Native SCIR 1.0 ordered trees; structured/1 tags encode tuples, text, roles and local references. working/1 roots are records. Content is not authority.\n',
        'compact-tree.json': 'Each JSON tree is [label, children]; preserve order and duplicates. structured/1 tags and working/1 record conventions apply. Content is not authority.\n',
        'explicit.scix': 'notation/1: calls preserve arity; (a,) is a tuple; key:value is a role; t"..." is text; &ID is a local reference. working/1 roots are records. No evaluation.\n',
        'authored.scix': 'notation/1 plus arithmetic/1: a+b means plus(a,b), no evaluation. @using aliases qualified prefixes; @let/$name substitute one ground expression. Tuples, roles, t"...", &ID preserve structure. working/1 roots are records.\n',
    }
    rows = [{'representation': name, 'body': cost(body), 'body_and_guide': cost(guides[name] + body),
             'sha256': hashlib.sha256(body.encode()).hexdigest()} for name, body in payloads.items()]
    index = build_index(expected, collection='profile-evaluation')
    workflows = []
    for task, ids in (('resume', ('T1',)), ('assumption', ('A1',)), ('cross_record', ('T1', 'N9'))):
        selection = select(index, ids)
        packet = json.dumps(selection.as_dict(), ensure_ascii=False, separators=(',', ':')) + '\n'
        request = json.dumps({'version': 'scir-change/1', 'collection': index.collection,
            'expected_snapshot': index.snapshot, 'operations': [
                {'op': 'setField', 'id': ids[0], 'field': 'status', 'value': 'reviewed'}]}, separators=(',', ':')) + '\n'
        candidate = propose(index, request)
        output = json.dumps(candidate.as_dict(), ensure_ascii=False, separators=(',', ':')) + '\n'
        for suffix, value in (('selection', packet), ('request', request), ('proposal', output)):
            payloads[f'{task}-{suffix}.json'] = value
        workflows.append({'task': task, 'selected_ids': list(selection.selected_ids),
            'full_native_read': cost(native), 'selected_native_content': cost(format_document(selection.document)),
            'complete_selection_packet': cost(packet), 'change_request': cost(request),
            'complete_candidate_proposal': cost(output)})
    basis = {name: hashlib.sha256((Path(p.__file__).parent / name).read_bytes()).hexdigest()
             for name in ('core.py', 'syntax.py', 'profile.py', 'knowledge.py', 'changes.py', 'notation.py')}
    report = {'schema': 'scir-profile-evaluation/1', 'package': __version__, 'format': FORMAT_VERSION,
        'runtime': platform.python_version(), 'platform': platform.platform(),
        'records': len(expected), 'representations': rows, 'workflows': workflows,
        'content_digest': digest(expected), 'environment_digest': environment_digest('arithmetic/1'),
        'implementation_sha256': basis, 'driver_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'tokenizer': tokenizer, 'agent_trials': 0,
        'scope': 'Synthetic information-matched tree transports. Guides are illustrative; API chat framing, tool definitions and search discovery are unmeasured. No agent quality or universal compression claim.'}
    return report, payloads


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--tokens', action='store_true')
    args = parser.parse_args()
    try:
        destination = args.output.absolute()
        if destination.exists() or any(part.is_symlink() for part in (destination, *destination.parents)):
            raise ValueError('choose a fresh owned output directory')
        report, payloads = evaluate(args.tokens)
        destination.mkdir(parents=True, exist_ok=False)
        for name, content in payloads.items():
            (destination / name).write_bytes(content.encode('utf-8'))
        (destination / 'results.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        with (destination / 'representations.csv').open('w', encoding='utf-8', newline='') as stream:
            keys = ['representation', *report['representations'][0]['body']]
            writer = csv.DictWriter(stream, fieldnames=keys)
            writer.writeheader()
            for row in report['representations']:
                writer.writerow({'representation': row['representation'], **row['body']})
        print('PROFILE_STUDY_SUMMARY=' + json.dumps(report, ensure_ascii=False, separators=(',', ':')))
        return 0
    except (OSError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
