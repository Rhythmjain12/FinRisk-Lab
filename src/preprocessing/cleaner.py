from pathlib import Path
import pandas as pd # type: ignore

def clean_prices(df):
    df_close =df.loc[:,("Close",slice(None))]
    df_close.columns=df_close.columns.droplevel(0)
    return df_close



