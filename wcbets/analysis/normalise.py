"""Per-90 normalisation. Pure functions, no I/O."""


def per90(total, minutes):
    if not minutes:
        return 0.0
    return round(total * 90.0 / minutes, 4)


def per90_row(row, stat_keys):
    out = dict(row)
    minutes = row.get("minutes", 0)
    for key in stat_keys:
        out[f"{key}_p90"] = per90(row.get(key, 0), minutes)
    return out
