# Main-based minimal C recovery candidate — HOLD, do not merge

Base main: 057d024dd46797a77e8893ab30e4f4cbd58655bf.
Source candidate: 521d50545e360cadf81db3226e5897cc6b39bf59.

This branch copies the C parsing/schema dependency closure, not PR #2 wholesale.
The existing parsers.py, main.py, airtable.py, repositories.py, state_machine.py,
Render config, dependencies and main's original tests are unchanged.
Archive, participant, withdrawal, readiness-policy and collection modules are excluded.
Runtime package init is included; parsers.py is an unchanged dependency.

The main state machine does NOT include the larger candidate's earlier clock
injection/pre-append-check change. Preserve this fact and all original assertions.
The full minimal-tree suite may expose old clock failures and a clock-argument
integration dependency. Do not delete tests or silently import that state-machine
patch to force green; explicitly review that dependency before release.

DryRunAirtableAdapter remains the only wired adapter. It writes local shadow SQLite,
not Airtable. No new external write adapter or schema migration is authorized here.
First post-release inspection must inspect the actual local shadow event payload,
schema_version=2, F/L raw/marker/magnitude, legacy projection and canonical hash.
External Airtable field compatibility remains untested and out of this release.
The schema reader is not yet forced into every historical audit path.

Release gates still open: full minimal-tree CI, clock dependency decision, active-race
check, live DRY_RUN/config, real SQLite backup and restore rehearsal, rollback reference,
scoped approval, deploy SHA/log/first-event verification and refreeze. No real backup,
network capture, scheduler changes, main merge or Render deployment occur in this stage.
An automatic main deployment means merging is a deployment action; never merge on a red
or unverified suite. C's evaluator remains a fixed shadow placeholder, not a betting model.
