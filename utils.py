import pandas as pd
import datetime

def parse_dt(dt_val):
    if pd.isna(dt_val) or dt_val is None or str(dt_val).strip() in ["", "TBD", "None", "nan", "NaT"]:
        return datetime.date.today(), datetime.time(12, 0)
    
    if isinstance(dt_val, (datetime.datetime, pd.Timestamp)):
        return dt_val.date(), dt_val.time()
        
    try:
        dt_obj = datetime.datetime.strptime(str(dt_val).strip(), "%d/%m/%Y %H:%M")
        return dt_obj.date(), dt_obj.time()
    except:
        try:
            dt_obj = pd.to_datetime(dt_val).to_pydatetime()
            return dt_obj.date(), dt_obj.time()
        except:
            return datetime.date.today(), datetime.time(12, 0)

def format_for_wa(dt_val):
    if pd.isna(dt_val) or dt_val is None or str(dt_val).strip() in ["", "TBD", "None", "nan", "NaT"]:
        return "TBD"
    if isinstance(dt_val, (datetime.datetime, pd.Timestamp)):
        return dt_val.strftime('%d/%m/%Y %H:%M')
    return str(dt_val)
