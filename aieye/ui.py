import sys, time, threading
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

def log(msg, color="reset", indent=0):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"{c(f'[{ts}]','dim')} {'  '*indent}{c(msg, color)}")

def section(title):
    print()
    print(c("─"*60, "cyan"))
    print(c(f"  {title}", "bold"))
    print(c("─"*60, "cyan"))

def ok(msg):   log(f"✅  {msg}", "green")
def warn(msg): log(f"⚠️   {msg}", "yellow")
def skip(msg): log(f"⏭   {msg} (cached)", "dim")
def fail(msg):
    log(f"❌  {msg}", "red")
    sys.exit(1)

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
        self._thread.start()
        return self

    def __exit__(self, *_):
        self._stop.set()
        self._thread.join()


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
            raw = input(c("  → Enter number (q to quit): ", "yellow")).strip()
            if raw.lower() in ("q", "quit", "exit"):
                raise KeyboardInterrupt
            idx = int(raw) - 1
            if 0 <= idx < len(choices):
                label, value, _ = choices[idx]
                ok(f"Selected: {label}")
                return value
            print(c("  Invalid choice — try again", "red"))
        except (KeyboardInterrupt, EOFError):
            print()
            print(c("  Cancelled.", "dim"))
            sys.exit(0)
        except ValueError:
            print(c("  Invalid — type a number, or q to quit", "red"))

def prompt_text(question, default=None):
    """Free text input. Returns None if blank and default is None."""
    print()
    hint = f" (leave blank to {default or 'skip'})" if default else " (leave blank to skip)"
    print(c(f"  {question}{hint}", "bold"))
    try:
        raw = input(c("  → ", "yellow")).strip()
        return raw if raw else default
    except (KeyboardInterrupt, EOFError):
        print()
        print(c("  Cancelled.", "dim"))
        sys.exit(0)

