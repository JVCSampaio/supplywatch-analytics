"""Every rejected source row keeps its original values and its rejection reasons."""

import numpy as np
import pandas as pd


class Gate:
    def __init__(self, frame, source):
        self.frame = frame.copy().reset_index(drop=True)
        self.source = source
        self.reasons = pd.Series("", index=self.frame.index, dtype=str)

    def reject(self, mask, reason):
        mask = pd.Series(mask, index=self.frame.index).fillna(True)
        self.reasons.loc[mask] += reason + ";"

    def key(self, column):
        self.reject(
            self.frame[column].isna() | self.frame[column].astype(str).str.strip().eq(""),
            "missing_" + column,
        )
        # Quarantine every occurrence: do not arbitrarily choose one conflicting record.
        self.reject(self.frame[column].duplicated(keep=False), "duplicate_" + column)

    def number(self, column, lower=0, upper=None, integer=False):
        values = pd.to_numeric(self.frame[column], errors="coerce")
        invalid = values.isna() | ~np.isfinite(values) | (values < lower)
        if upper is not None:
            invalid |= values > upper
        if integer:
            invalid |= values.mod(1).ne(0)
        self.reject(invalid, "invalid_" + column)
        return values

    def date(self, column):
        values = pd.to_datetime(self.frame[column], format="%Y-%m-%d", errors="coerce")
        self.reject(values.isna(), "invalid_" + column)
        return values

    def finish(self, cleaned):
        valid = self.reasons.eq("")
        rejected = self.frame.loc[~valid].copy()
        rejected["source"] = self.source
        rejected["source_row"] = rejected.index + 1
        rejected["reason"] = self.reasons.loc[~valid]
        return cleaned.loc[valid].copy(), rejected
