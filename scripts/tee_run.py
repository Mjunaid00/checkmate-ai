"""
Run a command, echo its output to the console AND append it to a log file.

Usage:
    python tee_run.py <logfile> -- <command> [args...]

Used by run-backend.cmd / run-frontend.cmd so that logs/backend.log and
logs/frontend.log always hold the last run's output (handy when a window
closed before you could read it).
"""
import datetime
import os
import shutil
import subprocess
import sys


def main() -> int:
    if len(sys.argv) < 4 or sys.argv[2] != "--":
        print(__doc__)
        return 2
    log_path = sys.argv[1]
    cmd = list(sys.argv[3:])

    # Resolve things like "npm" -> "npm.cmd" on Windows.
    resolved = shutil.which(cmd[0])
    if resolved:
        cmd[0] = resolved

    os.makedirs(os.path.dirname(os.path.abspath(log_path)), exist_ok=True)
    env = dict(os.environ, PYTHONUNBUFFERED="1", PYTHONUTF8="1", FORCE_COLOR="0", NO_COLOR="1")

    with open(log_path, "a", encoding="utf-8", errors="replace") as log:
        log.write(f"\n===== {datetime.datetime.now():%Y-%m-%d %H:%M:%S} start: {' '.join(cmd)}\n")
        log.flush()
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=env,
            )
        except FileNotFoundError as e:
            msg = f"Could not start {cmd[0]}: {e}\n"
            sys.stdout.write(msg)
            log.write(msg)
            return 127

        rc = 0
        try:
            assert proc.stdout is not None
            for line in proc.stdout:
                sys.stdout.write(line)
                sys.stdout.flush()
                log.write(line)
                log.flush()
            rc = proc.wait()
        except KeyboardInterrupt:
            # Ctrl+C reaches the child too; give it a moment, then make sure it is gone.
            try:
                rc = proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.terminate()
                rc = proc.wait()
        log.write(f"===== {datetime.datetime.now():%Y-%m-%d %H:%M:%S} exit code {rc}\n")
        return rc


if __name__ == "__main__":
    sys.exit(main())
