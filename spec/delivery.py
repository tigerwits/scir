"""Presentation of validated repository results, with their complete host guards."""
from scir import digest
from scir._profile_native import native
from scir.delivery import _bundle
from scir.knowledge import Index
from scir.notation import Limits as NotationLimits
from scir.profile import Limits, ProfileError


def present(index: Index, result: dict, *, kind: str, encoding: str = "native"):
    """Keep exact bases and source-owned write plans in the retrievable artifact."""
    if result["collection"] != index.collection or result["repository_contract"] != "scir-repository/2":
        raise ProfileError("repository delivery requires its validated collection result")
    guards = {"input_basis": result["input_basis"]["digest"]}
    header = {"kind": kind, "collection": index.collection, "guards": guards,
              "repository_contract": result["repository_contract"]}
    if kind == "selection":
        if result["source_snapshot"] != index.snapshot or not result["complete"]:
            raise ProfileError("repository selection is not from this complete snapshot")
        document = tuple(index.records[i].term for i in result["selected_ids"])
        header.update(source_snapshot=index.snapshot, requested_ids=result["requested_ids"],
                      content_scope="reference-closed-records")
    elif kind == "proposal":
        if result["before_snapshot"] != index.snapshot or not result["complete"]:
            raise ProfileError("repository proposal is not from this complete snapshot")
        final = tuple(native(t, one=True) for t in result["records"])
        if digest(final) != result["candidate_snapshot"]:
            raise ProfileError("repository candidate differs from its fingerprint")
        guards["commit_basis"] = result["commit_basis"]["digest"]
        final_ids = {t.args[0].symbol for t in final}
        document = tuple(t for t in final if t.args[0].symbol not in index.records
                         or t != index.records[t.args[0].symbol].term)
        header.update(before_snapshot=index.snapshot, candidate_snapshot=result["candidate_snapshot"],
                      content_scope="changed-records", context_complete=False, source_written=False,
                      deleted_ids=[i for i in index.records if i not in final_ids],
                      validation=result["validation"])
    else:
        raise ValueError("unsupported repository delivery kind")
    return _bundle(header, document, result, encoding=encoding, limits=Limits(),
                   notation_limits=NotationLimits(), max_packet_bytes=16_000_000,
                   max_artifact_bytes=16_000_000)
