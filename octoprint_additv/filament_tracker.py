from __future__ import absolute_import, division, print_function, unicode_literals
import re
from decimal import Decimal, getcontext

# Set maximum precision for Decimal calculations
getcontext().prec = 28

# Focused purely on PrusaSlicer defaults for now, with M83 relative E

class FilamentTracker:
    # Pre-compile all regex patterns as class variables for performance
    MOVE_RE = re.compile(r"^G[0-3](?:\s+|$)")
    E_COORD_RE = re.compile(r"(?:\s+|^)E([-+]?\d*\.?\d*)")
    RESET_E_RE = re.compile(r"^G92.*E0")

    def __init__(self):
        self.reset()

    def reset(self):
        """Reset all tracking variables"""
        self.total_extrusion = Decimal('0.0')    # Total accumulated extrusion for current job

    def process_line(self, line):
        """
        Process a single line of gcode and update job extrusion tracking.
        Returns the current total extrusion amount in mm for this job.
        """
        # Quick early exits for non-relevant lines
        if not line or line.startswith(';') or line.startswith('#'):
            return None

        # Process moves that might include extrusion
        if self.MOVE_RE.match(line):
            e_match = self.E_COORD_RE.search(line)
            if e_match:
                try:
                    e_value = Decimal(e_match.group(1))
                    self.total_extrusion += e_value  # Add all movements, positive and negative
                    return self.total_extrusion  # Return Decimal directly - JSON can handle it
                except ValueError:
                    pass  # Invalid float value, ignore
        
        return None
