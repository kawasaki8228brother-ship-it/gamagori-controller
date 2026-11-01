PHASE 1 AUDIT EVIDENCE ONLY - NO PR / NO MERGE / NO RENDER EXECUTION

Use INDEX.tsv for file names, exact byte sizes, SHA-256, trust and test states.
MANIFEST.json also records original hashes and the exact Git blob for each file.
The two v001 command TXT files are exact original bytes with no terminal LF.
All public logs are REDACTED or REDACTED_DERIVED and have different hashes from
their original raw logs. They are not byte-identical raw-log replacements.
Original raw log bytes were restored and verified against PR #6 before redaction.
The archived 248 tests and TLS observations were not independently rerun here.
The new v002 tests are Codex design checks only; Claude review remains pending.
The dummy output is not a measurement. Do not execute any candidate on Render.
No private key, live credential, authenticated URL, proxy URL or internal runtime
path is intentionally published in the log files. Generic filesystem literals
in the explicitly required exact command files are preserved, not log values.
C1 live-worker identity and startup safety remain UNVERIFIED. A2 is not performed.
HQ12 NEGATIVE_1/2 remain UNVERIFIED_NETWORK_ERROR ProxyError.

SHA256SUMS.txt covers every distributed file except itself. Its own hash and the
immutable evidence commit are reported in the handoff. Download raw files from
that commit; never reconstruct a command from Markdown or retype it.
