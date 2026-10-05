"""Repository-local document records and disposable views, over working/1.

This is not a Markdown importer, a runtime dialect, or a semantic fidelity checker.
Author records directly. The migration importer is not part of normal maintenance.
"""
from __future__ import annotations

from collections import defaultdict
import hashlib
import os
from pathlib import Path
import posixpath
import re
import shutil
from urllib.parse import unquote, urlsplit

from scir import Term, format_document
from scir.profile import ProfileError, read_fields, read_text, read_tuple

KINDS = frozenset(("Contract", "Guide", "Workflow", "Evidence", "Skill", "Source"))
FIELDS = frozenset(("document", "title", "level", "order", "origin", "links", "parent", "children", "sha256"))
MANIFEST = "spec/index.scir"
MAX_SHARDS = 128
MAX_DOCUMENTS = 256
MAX_BLOCKS = 4096
MARKDOWN = frozenset(("README.md", "AGENTS.md"))
LINK = re.compile(r"\[[^\]\n]*\]\(([^)\s]+)\)")
FENCE = re.compile(r"^```([\w-]*)[^\n]*\n(.*?)^```[ \t]*$", re.M | re.S)


def _leaf(value, role):
    if value.args:
        raise ProfileError(role + " must be a leaf")
    return value.symbol


def _integer(value, role, maximum=10000):
    raw = _leaf(value, role)
    if not re.fullmatch(r"0|[1-9][0-9]{0,5}", raw) or int(raw) > maximum:
        raise ProfileError(role + " must be a bounded canonical integer")
    return int(raw)


def source_paths(root):
    """Explicit shard inventory; no filesystem glob imports or silent fallback."""
    from scir._profile_native import native
    if __package__:
        from .locations import local_file, read_source
    else:
        from locations import local_file, read_source
    source = read_source(local_file(root, MANIFEST, ".scir", missing_error=FileNotFoundError))
    document = native(source)
    if format_document(document) != source or len(document) != 1:
        raise ProfileError("collection manifest must be one canonical collection")
    collection = document[0]
    if collection.symbol != "collection" or len(collection.args) < 2 or collection.args[0] != Term("scir-repository"):
        raise ProfileError("expected collection(scir-repository, shard(...), ...)")
    names = []
    for shard in collection.args[1:]:
        if shard.symbol != "shard" or len(shard.args) != 1:
            raise ProfileError("expected shard(path)")
        name = _leaf(shard.args[0], "shard path")
        local_file(root, name, ".scir", missing_error=FileNotFoundError)
        if name == MANIFEST or name in names:
            raise ProfileError("duplicate or recursive source shard")
        names.append(name)
    if len(names) > MAX_SHARDS:
        from scir.profile import LimitError
        raise LimitError("repository shard limit exceeded")
    return tuple(names)


def blocks(record):
    value = record.payload
    if value.symbol != "blocks":
        raise ProfileError("document payload must be blocks(...): " + record.id)
    if len(value.args) > MAX_BLOCKS:
        from scir.profile import LimitError
        raise LimitError("document block limit exceeded")
    return value.args


def validate(index):
    """Check document structure, identities and declared hierarchy; never execute code."""
    documents = defaultdict(list)
    for record in index.records.values():
        if record.kind not in KINDS:
            continue
        fields = dict(record.fields)
        required = {"document", "title", "level", "order", "ownership", "origin", "area"}
        if not required <= fields.keys() or fields["ownership"] != Term("record"):
            raise ProfileError("document records need explicit record ownership and metadata")
        name = _leaf(fields["document"], "document")
        parts = name.split("/")
        if (not name.endswith(".md") or "\\" in name or ":" in name
                or any(p in ("", ".", "..") for p in parts)):
            raise ProfileError("unsafe logical document name")
        if not read_text(fields["title"]):
            raise ProfileError("document title must be nonempty")
        if record.kind == "Source" and fields["level"] != Term("0"):
            raise ProfileError("a frozen source has no rendered heading")
        _integer(fields["level"], "level", 6)
        _integer(fields["order"], "order")
        origin = fields["origin"]
        if origin.symbol == "authored":
            if len(origin.args) != 1 or not read_text(origin.args[0]):
                raise ProfileError("new content needs an explicit authored provenance note")
        elif (origin.symbol != "origin" or len(origin.args) != 4 or any(x.args for x in origin.args)
                or not re.fullmatch(r"[a-f0-9]{40}", origin.args[0].symbol)
                or not re.fullmatch(r"[a-f0-9]{64}", origin.args[3].symbol)):
            raise ProfileError("origin needs pinned commit, original path, section and SHA-256")
        # Origin is historical data. It deliberately never opens its old Markdown path.
        if record.kind == "Source":
            raw = read_text(record.payload).encode("utf-8")
            if "sha256" not in fields or hashlib.sha256(raw).hexdigest() != _leaf(fields["sha256"], "source hash"):
                raise ProfileError("frozen source text hash mismatch")
        else:
            for block in blocks(record):
                args = block.args
                if block.symbol in ("paragraph", "quote", "formula", "note"):
                    if len(args) != 1:
                        raise ProfileError("text block needs one text value")
                    read_text(args[0])
                elif block.symbol == "code":
                    if len(args) != 2 or not re.fullmatch(r"[\w-]*", _leaf(args[0], "code language")):
                        raise ProfileError("code needs language and literal text")
                    read_text(args[1])
                elif block.symbol == "items":
                    if len(args) < 2 or args[0].symbol not in ("ordered", "unordered") or args[0].args:
                        raise ProfileError("items need a style and nonempty text items")
                    for item in args[1:]:
                        read_text(item)
                elif block.symbol == "table":
                    if len(args) < 2 or not args[0].args:
                        raise ProfileError("table needs header and at least one row")
                    width = len(args[0].args)
                    for row in args:
                        if row.symbol != "row" or len(row.args) != width:
                            raise ProfileError("table rows must have the same arity")
                        for cell in row.args:
                            read_text(cell)
                elif block.symbol == "projection":
                    if len(args) != 1 or args[0] not in (Term("query-spec"), Term("query-api")):
                        raise ProfileError("unknown document projection")
                elif block.symbol == "metadata":
                    if len(args) != 2 or record.kind != "Skill":
                        raise ProfileError("skill metadata needs name and description")
                    name_value = _leaf(args[0], "skill name")
                    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name_value) or len(name_value) > 64:
                        raise ProfileError("invalid skill name")
                    if not 1 <= len(read_text(args[1])) <= 1024:
                        raise ProfileError("invalid skill description")
                else:
                    raise ProfileError("unknown document block: " + block.symbol)
        if "parent" in fields:
            parent = fields["parent"]
            if parent.symbol != "scir.ref" or len(parent.args) != 1:
                raise ProfileError("parent needs an explicit reference")
            target = index.records[parent.args[0].symbol]
            target_fields = dict(target.fields)
            if (target.kind not in KINDS or target_fields["document"] != fields["document"]
                    or _integer(target_fields["level"], "parent level", 6) >= _integer(fields["level"], "level", 6)):
                raise ProfileError("parent must precede its child in the same document hierarchy")
        if "links" in fields:
            if read_fields(fields["links"]):
                raise ProfileError("navigation links must be a positional tuple")
            for link in read_tuple(fields["links"]):
                if link.symbol != "link" or len(link.args) != 2 or any(a.args for a in link.args):
                    raise ProfileError("navigation needs link(label, target); not a dependency")
        documents[name].append(record)
    if len(documents) > MAX_DOCUMENTS:
        from scir.profile import LimitError
        raise LimitError("logical document limit exceeded")
    for name, records in documents.items():
        order = [_integer(dict(r.fields)["order"], "order") for r in records]
        if len(set(order)) != len(order):
            raise ProfileError("duplicate document section order: " + name)
        if any(r.kind == "Source" for r in records) and len(records) != 1:
            raise ProfileError("frozen input must be the sole record for its logical document")
        # Gaps are allowed: inserting a section must not renumber stable neighbors.
    _validate_scope(index)
    return dict(documents)


def _validate_scope(index):
    """An owning section includes its complete descendant scope, without link floods."""
    children = defaultdict(set)
    fields = {key: dict(record.fields) for key, record in index.records.items()}
    for key, record in index.records.items():
        if record.kind in KINDS and "parent" in fields[key]:
            parent = fields[key]["parent"].args[0].symbol
            children[parent].add(key)
            if _integer(fields[parent]["order"], "parent order") >= _integer(fields[key]["order"], "child order"):
                raise ProfileError("parent must be ordered before its child")
    scoped = {value["source"].args[0].symbol for value in fields.values()
              if "source" in value and value["source"].symbol == "scir.ref"}
    pending = list(scoped)
    while pending:
        for child in children[pending.pop()] - scoped:
            scoped.add(child)
            pending.append(child)
    for key, record in index.records.items():
        if record.kind not in KINDS:
            continue
        value = fields[key].get("children")
        if value is not None:
            if read_fields(value):
                raise ProfileError("children must be a positional tuple")
            entries = read_tuple(value)
            if any(t.symbol != "scir.ref" or len(t.args) != 1 for t in entries):
                raise ProfileError("children need explicit references")
            declared = {t.args[0].symbol for t in entries}
            if len(declared) != len(entries) or declared != children[key]:
                raise ProfileError("children must name exactly the direct child sections")
        elif key in scoped and children[key]:
            raise ProfileError("an authoritative section must retain its complete child scope")
        if key in scoped and children[key]:
            dependencies = fields[key].get("dependsOn")
            if dependencies is None or not {Term("scir.ref", (Term(c),)) for c in children[key]} <= set(read_tuple(dependencies)):
                raise ProfileError("section dependencies must expose child changes to affected review")


def headings(source):
    counts, anchors = {}, set()
    for title in re.findall(r"^#{1,6} (.+)$", FENCE.sub("", source), re.M):
        slug = re.sub(r"[^\w\- ]", "", title.lower()).replace(" ", "-")
        count = counts.get(slug, 0)
        anchors.add(slug if not count else f"{slug}-{count}")
        counts[slug] = count + 1
    return anchors


def validate_links(index, root):
    """Resolve local navigation statically; never fetch a URL or execute a snippet."""
    if not any(r.kind in KINDS for r in index.records.values()):
        return set()  # Independent external-section fixtures do not use document records.
    if __package__:
        from .locations import local_file, read_source
    else:
        from locations import local_file, read_source
    rendered = rendered_documents(index, root)
    anchors = {name: headings(body) for name, body in rendered.items()}
    links = [(name, target) for name, body in rendered.items()
             for target in LINK.findall(FENCE.sub("", body))]
    for record in index.records.values():
        fields = dict(record.fields)
        if record.kind in KINDS and "links" in fields:
            links.extend((fields["document"].symbol, t.args[1].symbol) for t in read_tuple(fields["links"]))
    physical_inputs = set()
    for name, target in dict.fromkeys(links):
        parts = urlsplit(target)
        if parts.scheme or parts.netloc:
            continue  # Navigation, not an assertion that a remote site was verified.
        path = unquote(parts.path)
        if "\\" in path or ":" in path or path.startswith("/"):
            raise ProfileError("unsafe document link: " + target)
        resolved = posixpath.normpath(posixpath.join(posixpath.dirname(name), path)) if path else name
        if resolved == ".." or resolved.startswith("../"):
            raise ProfileError("document link escapes the repository: " + target)
        if resolved not in rendered:
            physical = root.resolve()
            for part in resolved.split("/"):
                physical = physical / part
                if physical.is_symlink():
                    raise ProfileError("symlink is not a document link: " + target)
            if physical.is_dir():
                if parts.fragment:
                    raise ProfileError("directory links cannot name document anchors")
                # A directory link needs a reproducible, nonempty directory in a
                # fixed-basis copy. Bind its bounded source inventory, not caches.
                for folder, dirs, files in os.walk(physical, followlinks=False):
                    dirs[:] = sorted(d for d in dirs if d not in (".git", "__pycache__", "build", "dist", ".venv", "venv")
                                     and not d.endswith(".egg-info"))
                    for item in (*dirs, *files):
                        entry = Path(folder) / item
                        if entry.is_symlink():
                            raise ProfileError("symlink is not a document link input")
                    for item in files:
                        if item.endswith((".pyc", ".pyo")):
                            continue
                        physical_inputs.add((Path(folder) / item).relative_to(root.resolve()).as_posix())
                        if len(physical_inputs) > 2048:
                            from scir.profile import LimitError
                            raise LimitError("document navigation input limit exceeded")
                continue
            physical = local_file(root, resolved, Path(resolved).suffix)
            physical_inputs.add(resolved)
            if parts.fragment and resolved not in anchors:
                anchors[resolved] = headings(read_source(physical))
        if parts.fragment and unquote(parts.fragment) not in anchors[resolved]:
            raise ProfileError("unknown document anchor: " + name + " -> " + target)
    return physical_inputs


def check_markdown_policy(paths):
    """Check an explicit source inventory, not generated or ignored build trees."""
    found = {str(path).replace("\\", "/") for path in paths
             if Path(str(path)).suffix.casefold() in (".md", ".markdown", ".mdx")}
    if found != MARKDOWN:
        raise ProfileError("only root README.md and AGENTS.md may be tracked Markdown: "
                           + ", ".join(sorted(found ^ MARKDOWN)))


def render_blocks(record, index):
    if record.kind == "Source":
        return read_text(record.payload)
    output = []
    for block in blocks(record):
        args = block.args
        if block.symbol in ("paragraph", "quote", "formula", "note"):
            output.append(read_text(args[0]))
        elif block.symbol == "code":
            language = "" if args[0].symbol == "plain" else args[0].symbol
            output.append("```" + language + "\n" + read_text(args[1]).rstrip("\n") + "\n```")
        elif block.symbol == "items":
            ordered = args[0].symbol == "ordered"
            output.append("\n".join((f"{i}. " if ordered else "- ") + read_text(item)
                                    for i, item in enumerate(args[1:], 1)))
        elif block.symbol == "table":
            rows = ["| " + " | ".join(read_text(c) for c in row.args) + " |" for row in args]
            rows.insert(1, "| " + " | ".join("---" for _ in args[0].args) + " |")
            output.append("\n".join(rows))
        elif block.symbol == "projection":
            if __package__:
                from .views import render_queries
            else:
                from views import render_queries
            # Keep the historical renderer's independent goldens intact. Its old
            # maintenance banner is not an instruction for a current disposable view.
            rendered = render_queries(index, examples=args[0].symbol == "query-api")
            output.append("\n".join(rendered.splitlines()[2:]).rstrip())
        elif block.symbol == "metadata":
            output.append("---\nname: " + args[0].symbol + "\ndescription: " + read_text(args[1]) + "\n---")
    return "\n\n".join(output) + ("\n" if output else "")


def render_document(index, name):
    records = [r for r in index.records.values() if r.kind in KINDS and dict(r.fields)["document"].symbol == name]
    if not records:
        raise ProfileError("unknown logical document: " + name)
    records.sort(key=lambda r: int(dict(r.fields)["order"].symbol))
    output = []
    for record in records:
        fields = dict(record.fields)
        level = int(fields["level"].symbol)
        if level:
            output.append("#" * level + " " + read_text(fields["title"]) + "\n")
        body = render_blocks(record, index)
        if body:
            output.append(body)
    return "\n".join(output)


def inventory(index):
    result = []
    for record in index.records.values():
        fields = dict(record.fields)
        result.append({"id": record.id, "kind": record.kind,
                       "title": read_text(fields["title"]) if "title" in fields else record.id,
                       "document": fields["document"].symbol if "document" in fields else None})
    return result


def rendered_documents(index, root):
    names = dict.fromkeys(dict(r.fields)["document"].symbol for r in index.records.values() if r.kind in KINDS)
    result = {name: render_document(index, name) for name in names}
    for name in MARKDOWN:
        result[name] = (root / name).read_text(encoding="utf-8")
    return result


def export(index, root, destination, *, skill=None):
    """Create a fresh external view from checked input bytes; no source writes.

    Parent aliases (for example macOS /tmp) are resolved once. The resolved target
    must be fresh and outside the checkout. This is not a filesystem transaction.
    """
    if __package__:
        from .locations import local_file, read_source
    else:
        from locations import local_file, read_source
    from scir._profile_native import native
    from scir.changes import ConflictError
    from scir.profile import LimitError

    root = root.resolve()
    if destination.is_symlink():
        raise ProfileError("export destination may not be a symlink")
    destination = destination.resolve()
    if destination.exists() or destination.is_relative_to(root):
        raise ProfileError("export requires a fresh destination outside the checkout")
    if skill not in (None, "scir", "scir-migrate"):
        raise ProfileError("unknown portable skill")

    inputs, total = {}, 0

    def read(name):
        nonlocal total
        if name not in inputs:
            raw = read_source(local_file(root, name, Path(name).suffix)).encode("utf-8")
            total += len(raw)
            if len(inputs) >= 2048 or total > 32_000_000:
                raise LimitError("document export input limit exceeded")
            inputs[name] = raw
        return inputs[name]

    read(MANIFEST)
    names = source_paths(root)
    source_document = tuple(t for name in names for t in native(read(name).decode("utf-8")))
    if source_document != index.document:
        raise ConflictError("export index is stale; reload the authoritative collection")
    for name in MARKDOWN:
        read(name)
    logical = rendered_documents(index, root)
    logical.update((name, inputs[name].decode("utf-8")) for name in MARKDOWN)
    prefix = "skills/" + skill + "/" if skill else ""
    outputs = {}
    for name, body in logical.items():
        if name.startswith(prefix):
            target = name[len(prefix):]
            if any(part in ("", ".", "..") for part in target.split("/")):
                raise ProfileError("unsafe export path")
            outputs[target] = body.encode("utf-8")
    # Copy the closed portable skill or the complete source-reference material.
    bases = [root / "skills" / skill] if skill else [root / name for name in
        ("src", "spec", "docs", "examples", "skills", "proofs", "tools", "tests", ".github")]
    for base in bases:
        if base.is_symlink():
            raise ProfileError("export source may not contain symlinks")
        for path in sorted(base.rglob("*")):
            if any(part in ("__pycache__", ".git") or part.endswith(".egg-info") for part in path.parts):
                continue
            if path.is_symlink():
                raise ProfileError("export source may not contain symlinks")
            if path.is_file() and path.suffix not in (".pyc", ".pyo", ".md"):
                name = path.relative_to(base if skill else root).as_posix()
                if name in outputs:
                    raise ProfileError("duplicate export destination")
                outputs[name] = read(path.relative_to(root).as_posix())
    if not skill:
        outputs["LICENSE"] = read("LICENSE")

    def unchanged():
        for name, expected in inputs.items():
            if read_source(local_file(root, name, Path(name).suffix)).encode("utf-8") != expected:
                raise ConflictError("export input changed: " + name)

    unchanged()
    destination.mkdir(parents=True)
    try:
        for name, raw in outputs.items():
            path = destination / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
        unchanged()
    except BaseException:
        # Only this fresh destination is owned here. Never clean an existing path.
        shutil.rmtree(destination)
        raise
    return {"version": "scir-document-export/1", "files": len(outputs),
            "source_snapshot": index.snapshot, "skill": skill,
            "input_sha256": {name: hashlib.sha256(raw).hexdigest() for name, raw in sorted(inputs.items())},
            "sha256": {name: hashlib.sha256(raw).hexdigest() for name, raw in sorted(outputs.items())}}
