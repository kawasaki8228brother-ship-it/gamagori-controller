"""Offline N1 lineage checks; historical lists and source archives stay unchanged."""
import difflib
import hashlib
import json
from pathlib import Path
import re
import types
import unittest

from model11.revision_v003.course import COURSE_POLICIES, canonical_hash


ROOT = Path(__file__).resolve().parents[1]
TARGET = "model11/revision_v003/course.py"
ARCHIVE = "revision_v004/references/course_v003_original.py.txt"
OLD_SHA = "48b53e1b372c9c8b63027567d920514ac4e23668f0373d9f4f9a559789f0f66b"
NEW_SHA = "ca28937aa1784fc37fa9a9539e0219d27570390ced01b3a0a2f77268238ed264"
OLD_BLOB = "e4853916e7d8b0f335a7c49d6e4855c40f51cff1"
NEW_BLOB = "59d9e564d9370655b5deb84cfb61bd26ac1c2760"
COMMITS = {"v003": "62721c20676177bac171f97b0488412b07b63594",
           "v004": "df807089f5fd27517109f9bd38b6c55f9415600e",
           "v005": "f3c3a3eb17073bd0a127bb943f4eda21e407cf2d"}


def facts(relative):
    raw = (ROOT / relative).read_bytes()
    return len(raw), hashlib.sha256(raw).hexdigest(), hashlib.sha1(
        b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()


def sum_rows(relative):
    raw = (ROOT / relative).read_bytes()
    rows = []
    for line in raw.decode("ascii").splitlines():
        expected, path = line.split("  ", 1)
        if not re.fullmatch(r"[0-9a-f]{64}", expected) or path.startswith("/") or ".." in Path(path).parts:
            raise AssertionError("UNSAFE_OR_INVALID_HISTORICAL_SUM_ROW")
        rows.append((expected, path))
    if len({path for _, path in rows}) != len(rows):
        raise AssertionError("DUPLICATE_HISTORICAL_SUM_ROW")
    return rows


class N1LineageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = json.loads((ROOT / "shadow_preparation_v006/results/N1_LINEAGE.json").read_bytes())
        cls.v3 = json.loads((ROOT / "revision_v003/MANIFEST_V003.json").read_bytes())
        cls.v4 = json.loads((ROOT / "revision_v004/MANIFEST_V004.json").read_bytes())
        cls.v5 = json.loads((ROOT / "shadow_launch_v005/MANIFEST_V005.json").read_bytes())

    def test_all46_v003_rows_recompute_as45_direct_matches_one_explained_supersession(self):
        rows = sum_rows("revision_v003/SHA256SUMS_V003.txt")
        self.assertEqual(len(rows), 46)
        mismatches = [(path, expected, facts(path)[1]) for expected, path in rows if facts(path)[1] != expected]
        self.assertEqual(mismatches, [(TARGET, OLD_SHA, NEW_SHA)])
        self.assertEqual(sum(facts(path)[1] == expected for expected, path in rows), 45)
        self.assertEqual(self.report["v003_sumlist"]["entries"], 46)
        self.assertEqual(self.report["v003_sumlist"]["direct_matches"], 45)
        self.assertEqual(self.report["v003_sumlist"]["unexplained_mismatches"], 0)

    def test45_payload_vs46_sum_entries_is_manifest_inclusion_not_a_missing_file(self):
        payload = {row["path"].removeprefix("development/model11/") for row in self.v3["added_payload_files"]}
        listed = {path for _, path in sum_rows("revision_v003/SHA256SUMS_V003.txt")}
        self.assertEqual(len(payload), 45)
        self.assertEqual(self.v3["added_payload_count"], 45)
        self.assertEqual(listed - payload, {"revision_v003/MANIFEST_V003.json"})
        self.assertEqual(payload - listed, set())
        self.assertNotIn("revision_v003/SHA256SUMS_V003.txt", listed)

    def test_old_archive_matches_declared_parent_git_blob_and_original_v003_sha(self):
        self.assertEqual(facts(ARCHIVE), (17860, OLD_SHA, OLD_BLOB))
        old = next(row for row in self.v3["added_payload_files"] if row["path"].endswith("/" + TARGET))
        parent = self.v4["changed_source_parent"]
        archived = next(row for row in self.v4["payload_files"] if row["path"].endswith("/" + ARCHIVE))
        for declared in (old, parent, archived):
            self.assertEqual((declared["bytes"], declared["sha256"], declared["git_blob"]), facts(ARCHIVE))

    def test_current_source_matches_v004_and_v005_manifest_git_blob(self):
        self.assertEqual(facts(TARGET), (20110, NEW_SHA, NEW_BLOB))
        v4 = next(row for row in self.v4["payload_files"] if row["path"].endswith("/" + TARGET))
        v5 = next(row for row in self.v5["files"] if row["path"].endswith("/" + TARGET))
        for declared in (v4, v5):
            self.assertEqual((declared["bytes"], declared["sha256"], declared["git_blob"]), facts(TARGET))
        self.assertEqual(v4["status"], "modified")

    def test_preserved_n1_diff_recreates_the_exact_current_source_difference(self):
        generated = "".join(difflib.unified_diff((ROOT / ARCHIVE).read_text().splitlines(keepends=True),
            (ROOT / TARGET).read_text().splitlines(keepends=True), fromfile="a/" + TARGET, tofile="b/" + TARGET)).encode("ascii")
        self.assertEqual(generated, (ROOT / "revision_v004/N1.diff").read_bytes())
        self.assertEqual(hashlib.sha256(generated).hexdigest(),
                         "e4c279b65a08d044bf6931885679435da8750261e74ba57dd47c2ea8f2d9248e")

    def test_all_three_course_policy_objects_and_hashes_are_unchanged(self):
        archived = types.ModuleType("model11.revision_v003._lineage_archive_test")
        archived.__package__ = "model11.revision_v003"
        exec(compile((ROOT / ARCHIVE).read_bytes(), "course_v003_original.py.txt", "exec"), archived.__dict__)
        self.assertEqual(COURSE_POLICIES, archived.COURSE_POLICIES)
        self.assertEqual(len(COURSE_POLICIES), 3)
        for name, policy in COURSE_POLICIES.items():
            current = canonical_hash(policy)
            self.assertEqual(current, archived.canonical_hash(archived.COURSE_POLICIES[name]))
            self.assertEqual(current, self.v4["policy_hashes"][name]["before"])
            self.assertEqual(current, self.v4["policy_hashes"][name]["after"])
            observed = self.report["local_policy_recomputation"][name]
            self.assertTrue(observed["unchanged"])
            self.assertEqual(current, observed["archive_sha256"])
            self.assertEqual(current, observed["current_sha256"])

    def test_historical_sumfiles_are_preserved_and_v004_verifies16_of16(self):
        self.assertEqual(facts("revision_v003/SHA256SUMS_V003.txt")[:2],
                         (4928, "4e0bbddde7ab29596b1185fbdf3edb186e67d07544d636ebd66a29af42ba1b9b"))
        self.assertEqual(facts("revision_v004/SHA256SUMS_V004.txt")[:2],
                         (1634, "56286d3e9689a163c490ef752afc619d87a7c1bca3c2f6c564c3317b7ca50781"))
        rows = sum_rows("revision_v004/SHA256SUMS_V004.txt")
        self.assertEqual(len(rows), 16)
        for expected, path in rows:
            self.assertEqual(facts(path)[1], expected)
        self.assertIn((NEW_SHA, TARGET), rows)
        self.assertIn((OLD_SHA, ARCHIVE), rows)

    def test_new_evidence_enumerates_every_original_sum_entry_and_never_claims_remote_authentication(self):
        expected = sum_rows("revision_v003/SHA256SUMS_V003.txt")
        rows = self.report["entry_checks"]
        self.assertEqual(len(rows), 46)
        for index, (record, (old_sha, path)) in enumerate(zip(rows, expected), 1):
            with self.subTest(entry=index):
                count, digest, blob = facts(path)
                self.assertEqual((record["entry"], record["path"], record["expected_v003_sha256"]), (index, path, old_sha))
                self.assertEqual((record["bytes"], record["sha256"], record["git_blob"]), (count, digest, blob))
                self.assertEqual(record["direct_v003_match"], old_sha == digest)
                self.assertIn(COMMITS["v003"], record["v003_original_raw_url"])
                self.assertIn(COMMITS["v005"], record["v005_current_raw_url"])
        self.assertEqual(self.report["commits"], COMMITS)
        self.assertIs(self.report["proof_scope"]["remote_fetch_in_this_subtask"], False)
        self.assertEqual(self.report["proof_scope"]["independent_authenticity"], "NOT_ESTABLISHED_BY_SELF_HASH_OR_MANIFEST_ALONE")
        self.assertIs(self.report["production_go"], False)


if __name__ == "__main__":
    unittest.main()
