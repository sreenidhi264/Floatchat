# qc_filter.py
# Filters and cleans measurements based on Argo Quality Control (QC) flags

import config

# Use a frozenset for O(1) `in` lookups instead of a list
_ACCEPTED = frozenset(config.ACCEPTED_QC_FLAGS)

# QC flag values that explicitly mean "no QC performed" — NOT the same as bad data
_MISSING_QC = frozenset({9, None})


def _is_accepted(qc):
    """
    Three-way QC gate:
      - Explicitly GOOD  (flag 1 or 2)  → True  (keep value)
      - Missing / No QC  (flag 9 or None) → True  (benefit of the doubt, keep value)
      - Explicitly BAD   (flag 3 or 4)  → False (discard value)

    The original code treated missing QC the same as bad QC, which silently
    dropped valid measurements that simply had no quality flag assigned yet.
    """
    if qc in _ACCEPTED:
        return True       # Explicitly good
    if qc in _MISSING_QC:
        return True       # No QC available — keep it, don't assume it's bad
    return False           # Explicitly flagged bad (3=probably bad, 4=bad)


def filter_measurements(measurements):
    """
    Applies QC flag filtering on a list of measurement dictionaries.

    Rules:
      1. Pressure QC: Only discard the whole row if pressure is *explicitly*
         flagged bad (3 or 4). If pressure QC is missing (None/9), keep the row —
         we cannot assume the depth is wrong just because no flag was assigned.
      2. Per-parameter: Keep the value unless its QC flag is explicitly bad.
         Missing QC (None/9) → keep the value.
      3. If ALL science parameters are None after filtering, discard the row.
    """
    filtered = []

    for row in measurements:
        # ── Rule 1: Pressure check ─────────────────────────────────────────────
        p_qc = row.get("pressure_qc")
        # Only skip if pressure is explicitly bad — missing QC gets a pass
        if p_qc is not None and p_qc not in _MISSING_QC and p_qc not in _ACCEPTED:
            continue   # Pressure explicitly flagged bad → depth level unreliable

        # ── Extract science parameters ─────────────────────────────────────────
        temp = row.get("temperature");  t_qc = row.get("temperature_qc")
        sal  = row.get("salinity");     s_qc = row.get("salinity_qc")
        oxy  = row.get("oxygen");       o_qc = row.get("oxygen_qc")
        chla = row.get("chlorophyll");  c_qc = row.get("chlorophyll_qc")

        # ── Rule 2: Keep values unless explicitly flagged bad ──────────────────
        clean_temp  = temp  if _is_accepted(t_qc) else None
        clean_sal   = sal   if _is_accepted(s_qc) else None
        clean_oxy   = oxy   if _is_accepted(o_qc) else None
        clean_chla  = chla  if _is_accepted(c_qc) else None

        # ── Rule 3: Skip rows with zero surviving science data ─────────────────
        if (clean_temp is None and
                clean_sal is None and
                clean_oxy is None and
                clean_chla is None):
            continue

        # Keep original QC flags in the stored row for DB auditing
        filtered.append({
            "pressure":       row["pressure"],
            "pressure_qc":    p_qc,
            "temperature":    clean_temp,
            "temperature_qc": t_qc,
            "salinity":       clean_sal,
            "salinity_qc":    s_qc,
            "oxygen":         clean_oxy,
            "oxygen_qc":      o_qc,
            "chlorophyll":    clean_chla,
            "chlorophyll_qc": c_qc,
        })

    return filtered
