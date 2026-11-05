"""Read-only local reporting. No startup, fit, save, source client or cloud API."""
import argparse
import json

from ..cli import _load


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError("INVALID_COMMAND_OR_OPTION")


def main(argv=None):
    parser = _Parser(description="Offline refinements only; default DISABLED")
    parser.add_argument("command", nargs="?", default="status", choices=("status", "schedule", "pit", "pilot"))
    parser.add_argument("--enable-offline", action="store_true")
    parser.add_argument("--input")
    parser.add_argument("--schedule")
    parser.add_argument("--predictions")
    parser.add_argument("--target-date")
    parser.add_argument("--expected-storage-id")
    parser.add_argument("--roster")
    parser.add_argument("--observations")
    parser.add_argument("--baseline-id")
    parser.add_argument("--baseline-version")
    parser.add_argument("--model-id")
    parser.add_argument("--model-version")
    parser.add_argument("--roster-complete", action="store_true")
    try:
        args = parser.parse_args(argv)
    except ValueError:
        print(json.dumps({"status": "HOLD", "reasons": ["INVALID_COMMAND_OR_OPTION"],
                          "application_status": "HOLD", "production_go": False}, sort_keys=True))
        return 2
    result = {"status": "DISABLED", "application_status": "HOLD", "production_go": False}
    try:
        if args.enable_offline and args.command != "status":
            if args.command == "schedule":
                from .schedule import audit_manifest_coverage
                result = audit_manifest_coverage(_load(args.schedule), _load(args.predictions),
                    target_date=args.target_date, expected_storage_id=args.expected_storage_id)
            elif args.command == "pit":
                from .point_in_time import audit_point_in_time
                result = audit_point_in_time(_load(args.input))
            else:
                from .pilot import summarize_pilot
                result = summarize_pilot(None if args.roster is None else _load(args.roster),
                    _load(args.observations), baseline_id=args.baseline_id, baseline_version=args.baseline_version,
                    model_id=args.model_id, model_version=args.model_version, roster_complete=args.roster_complete)
        result["application_status"] = "HOLD"
        result["production_go"] = False
        print(json.dumps(result, sort_keys=True, ensure_ascii=True, allow_nan=False))
        return 2 if result.get("status") in ("HOLD", "STOP") else 0
    except Exception:
        print(json.dumps({"status": "HOLD", "reasons": ["LOCAL_OFFLINE_INPUT_UNVERIFIED"],
                          "application_status": "HOLD", "production_go": False}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
