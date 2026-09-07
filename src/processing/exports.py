"""Keep untrusted text literal when downloaded CSVs are opened in a spreadsheet."""
import pandas as pd


def spreadsheet_csv(frame: pd.DataFrame) -> str:
    def literal(value):
        if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
            return "'" + value
        return value
    safe = frame.copy()
    for column in safe.select_dtypes(include=["object", "string"]).columns:
        safe[column] = safe[column].map(literal)
    safe.columns = [literal(c) for c in safe.columns]
    return safe.to_csv(index=False)
