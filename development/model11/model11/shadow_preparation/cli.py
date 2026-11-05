"""Read-only local preparation reports; no writer, host setup or Shadow start."""
import argparse
import json

from ..cli import _load
from ..shadow_launch.cli import _capture
from .capture_review import audit_capture_preparation, make_open_mapping_template
from .evaluation_design import proposed_options
from .runtime_probe import probe_local_runtime


class _PreparationParser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError("INVALID_COMMAND_OR_OPTION")


def main(argv=None):
    parser = _PreparationParser(description="Offline preparation only; default DISABLED")
    parser.add_argument("command", nargs="?", default="status",
                        choices=("status", "inventory", "f5", "capture", "coverage", "runtime"))
    parser.add_argument("--enable-offline", action="store_true")
    parser.add_argument("--synthetic-validation", action="store_true")
    parser.add_argument("--mapping")
    parser.add_argument("--capture")
    parser.add_argument("--schedule")
    parser.add_argument("--predictions")
    parser.add_argument("--target-date")
    parser.add_argument("--expected-storage-id")
    parser.add_argument("--storage-directory")
    try:
        args = parser.parse_args(argv)
    except ValueError:
        print(json.dumps({"status": "HOLD", "application_status": "HOLD", "production_go": False,
                          "reasons": ["INVALID_COMMAND_OR_OPTION"]}, sort_keys=True))
        return 2
    result = {"status": "DISABLED", "application_status": "HOLD", "production_go": False}
    try:
        if args.enable_offline and args.command != "status":
            if args.command == "inventory":
                result = make_open_mapping_template()
            elif args.command == "f5":
                result = proposed_options()
            elif args.command == "capture":
                if not args.synthetic_validation:
                    result = audit_capture_preparation()
                else:
                    capture = _load(args.capture)
                    if (not isinstance(capture, dict) or capture.get("data_classification") != "SYNTHETIC_ONLY"
                            or capture.get("synthetic") is not True):
                        result = audit_capture_preparation(None, capture, synthetic_validation=True)
                    else:
                        result = audit_capture_preparation(_load(args.mapping), _capture(capture),
                                                           synthetic_validation=True)
            elif args.command == "coverage":
                from .coverage import audit_schedule_coverage
                result = audit_schedule_coverage(_load(args.schedule), _load(args.predictions),
                                                  target_date=args.target_date,
                                                  expected_storage_id=args.expected_storage_id)
            else:
                result = probe_local_runtime(args.storage_directory, enable_offline=args.synthetic_validation,
                    classification="SYNTHETIC_ONLY" if args.synthetic_validation else None)
        result["application_status"] = "HOLD"
        result["production_go"] = False
        print(json.dumps(result, sort_keys=True, ensure_ascii=True, allow_nan=False))
        if result.get("software_check") == "PASS":
            return 0
        return 2 if result.get("status") in ("HOLD", "STOP") else 0
    except Exception:
        print(json.dumps({"status": "HOLD", "application_status": "HOLD", "production_go": False,
                          "reasons": ["LOCAL_PREPARATION_INPUT_UNVERIFIED"]}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
