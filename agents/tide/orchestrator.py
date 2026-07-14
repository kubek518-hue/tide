"""ORCHESTRATOR — wakes agents, passes the baton, logs every run (Policy C1).

Usage:
  python -m tide.orchestrator scout analyst          # signal collection + scoring
  python -m tide.orchestrator publisher              # weekly digest
  python -m tide.orchestrator scout analyst publisher
"""
import sys
import traceback

from . import db
from .scout import scout
from .analyst import analyst
from .publisher import publisher
from .coach import coach
from .bookkeeper import bookkeeper
from .sentinel import sentinel
from .creative import creative
from . import auditor
from .operations import operations
from .recruiter import recruiter
from .ripple import ripple

# All nine agents are active. Built as one piece; switched on one by one.
# Each has a package folder with a scaffold explaining its contract.

AGENTS = {
    "scout": lambda run_id: scout.run(),
    "analyst": lambda run_id: analyst.run(run_id),
    "publisher": lambda run_id: publisher.run(),
    "coach": lambda run_id: coach.run(run_id),
    "bookkeeper": lambda run_id: bookkeeper.run(run_id),
    "sentinel": lambda run_id: sentinel.run(run_id),
    "creative": lambda run_id: creative.run(run_id),
    "audit": lambda run_id: auditor.run(run_id),
    "operations": lambda run_id: operations.run(run_id),
    "recruiter": lambda run_id: recruiter.run(run_id),
    "ripple": lambda run_id: ripple.run(run_id),   # EXPERIMENT — grades itself
}


def main(argv: list[str]) -> int:
    names = [a for a in argv if a in AGENTS]
    if not names:
        print(f"usage: python -m tide.orchestrator [{'|'.join(AGENTS)}] ...")
        return 2

    exit_code = 0
    for name in names:
        run_id = db.start_run(name)
        try:
            stats = AGENTS[name](run_id)
            db.finish_run(run_id, ok=True, stats=stats or {})
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            db.finish_run(run_id, ok=False, stats={}, error=str(e))
            exit_code = 1
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
