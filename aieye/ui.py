import sys, time, threading
from pathlib import Path
from datetime import datetime

# COLOURS & LOGGING

C = {
    "reset":  "\033[0m",
    "cyan":   "\033[96m",
    "green":  "\033[92m",
    "yellow": "\033[93m",
    "red":    "\033[91m",
    "bold":   "\033[1m",
    "dim":    "\033[2m",
    "white":  "\033[97m",
    "purple": "\033[95m",
}

def c(text, col): return f"{C.get(col,'')}{text}{C['reset']}"

# EVENTS: everything the pipeline reports is also sent to listeners as a plain dict, so a UI (the web app) can show
# it live. With no listener registered nothing changes: the terminal output is exactly as before.

_listeners = []

def add_listener(fn):
    """fn(event: dict) is called for every log line / section / spinner / cost / progress update."""
    _listeners.append(fn)

def remove_listener(fn):
    if fn in _listeners:
        _listeners.remove(fn)

def emit(kind, **data):
    """kind: log | section | spin | cost | progress | review. Listener errors never break the pipeline."""
    if not _listeners:
        return
    ev = {"kind": kind, "time": datetime.now().isoformat(timespec="seconds"), **data}
    for fn in list(_listeners):
        try:
            fn(ev)
        except Exception:
            pass

class AieyeError(SystemExit):
    """A user-facing, expected failure (missing key, bad setting, no credits...). It is a SystemExit, so the
    terminal behaves exactly as before (message printed, exit code 1); the web app catches it and shows `.message`."""
    def __init__(self, message):
        super().__init__(1)
        self.message = message

def artifact(kind, path=None, **data):
    """Tell a UI about something the run just made (script, image, video) so it can preview it. `path` is sent relative
    to the output folder; the web server only serves files inside it."""
    if not _listeners:
        return
    rel = None
    if path is not None:
        try:
            from .config import OUTPUT_DIR
            rel = str(Path(path).resolve().relative_to(Path(OUTPUT_DIR).resolve()))
        except Exception:
            rel = None
    emit("artifact", what=kind, path=rel, **data)

def log(msg, color="reset", indent=0):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"{c(f'[{ts}]','dim')} {'  '*indent}{c(msg, color)}")
    emit("log", message=msg, color=color, indent=indent)

def section(title):
    emit("section", title=title)
    print()
    print(c("─"*60, "cyan"))
    print(c(f"  {title}", "bold"))
    print(c("─"*60, "cyan"))

def ok(msg):   log(msg, "green")
def warn(msg): log(f"Warning: {msg}", "yellow")
def skip(msg): log(f"{msg} (cached)", "dim")
def fail(msg):
    log(f"Error: {msg}", "red")
    raise AieyeError(msg)

# SPINNER — shows while any blocking call runs

class Spinner:
    FRAMES = ["⠋","⠙","⠹","⠸","⠼","⠴","⠦","⠧","⠇","⠏"]

    def __init__(self, label):
        self.label   = label
        self._stop   = threading.Event()
        self._thread = threading.Thread(target=self._spin, daemon=True)

    def _spin(self):
        i = 0
        while not self._stop.is_set():
            frame = self.FRAMES[i % len(self.FRAMES)]
            print(f"\r  {c(frame,'cyan')} {c(self.label,'dim')}   ", end="", flush=True)
            time.sleep(0.08)
            i += 1
        print(f"\r{' '*60}\r", end="", flush=True)

    def __enter__(self):
        emit("spin", label=self.label, state="start")
        self._thread.start()
        return self

    def __exit__(self, *_):
        self._stop.set()
        self._thread.join()
        emit("spin", label=self.label, state="stop")


def spin(label):
    """Use as: with spin('Doing thing...'): do_thing()"""
    return Spinner(label)

def prompt_choice(question, choices):
    """Show numbered choices, return selected value."""
    print()
    print(c(f"  {question}", "bold"))
    for i, (label, value, hint) in enumerate(choices, 1):
        print(f"  {c(str(i),'cyan')}  {c(label,'white')}  {c(hint,'dim')}")
    print()
    while True:
        try:
            raw = input(c("  Enter number (q to quit): ", "yellow")).strip()
            if raw.lower() in ("q", "quit", "exit"):
                raise KeyboardInterrupt
            idx = int(raw) - 1
            if 0 <= idx < len(choices):
                label, value, _ = choices[idx]
                ok(f"Selected: {label}")
                return value
            print(c("  Invalid choice, try again", "red"))
        except (KeyboardInterrupt, EOFError):
            print()
            print(c("  Cancelled.", "dim"))
            sys.exit(0)
        except ValueError:
            print(c("  Type a number, or q to quit", "red"))

def prompt_text(question, default=None):
    """Free text input. Returns None if blank and default is None."""
    print()
    hint = f" (leave blank to {default or 'skip'})" if default else " (leave blank to skip)"
    print(c(f"  {question}{hint}", "bold"))
    try:
        raw = input(c("  > ", "yellow")).strip()
        return raw if raw else default
    except (KeyboardInterrupt, EOFError):
        print()
        print(c("  Cancelled.", "dim"))
        sys.exit(0)

