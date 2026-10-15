"""Running API cost of the video currently being built."""
from .ui import log

_total = 0.0

def reset():
    global _total
    _total = 0.0

def total():
    return _total

def track(label, amount):
    global _total
    _total += amount
    log(f"💰  [{label}] ${amount:.4f}  |  total: ${_total:.4f}", "yellow")
