"""Live v4.19.40 misses: figures, the full Bay procedure, an optional photo, the procedure list, and the freeze-sensor shorthand."""
import unittest

from pathlib import Path

import manual_figures as mf

CAT = "Plumbing / Toilets"
MODEL = "Style II 42070"
CITE = "📖 Source: Thetford Style II OM Permanent RV Toilet 42088, page 3"


def _procedure_history(first_step):
    return [
        {"role": "user", "content": "toilet leaks under the flush lever"},
        {"role": "assistant", "content": "Back of the toilet: check the water supply line."},
        {"role": "user", "content": "Supply is tight. The water valve weeps at the pedal."},
        {"role": "assistant", "content": "Check whether the vacuum breaker leaks while flushing."},
        {"role": "user", "content": "Vacuum breaker is dry. No leak there."},
        {"role": "assistant", "content": first_step},
    ]


class TestBundledThetfordFigures(unittest.TestCase):
    pass



if __name__ == "__main__":
    unittest.main()
