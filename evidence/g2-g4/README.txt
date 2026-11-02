G2-G4 DESIGN/ISOLATION EVIDENCE - NO PRODUCTION EXECUTION GO

Target PR #6 head: 97640c8c307fed8eaa19f2557f5057ccade18da1.
See G2-G4-PLAN.txt for safety, STOP conditions and the iPhone abort procedure.
INDEX.tsv lists each command, source, document, log, reference and dummy sample.
COMMANDS.json gives command/payload byte counts and SHA-256. All candidate TXT
files are ASCII one-line originals with no terminal LF; copy immutable raw files.
Decoded payloads are included in source/ and reconstruct exactly with the offline
verify-commands.py. Every new Render candidate uses the same v002 output frame.
The preserved A5 v001 is an unmodified reference, not a new execution candidate.

The raw submitted logs are safe synthetic-fixture observations, with no redaction
and no live secrets/paths. They are not Render or external NEGATIVE_1/2 results.
No fixture private key or database file is published. Existing SHM physical changes
are explicitly distinguished from protected source DB/WAL data changes.
25 Codex isolated cases passed. Claude independent review is still PENDING.
G1 is only recorded as CLOSED per HQ13; its private evidence is not accessed.

SHA256SUMS.txt covers all files except itself. Its hash is given in the handoff.
This package does not authorize Render read, backup creation, TLS probing, merge,
deploy, suspend/resume, production/task/model/BOX/Freeze/POINTER/canonical changes.
