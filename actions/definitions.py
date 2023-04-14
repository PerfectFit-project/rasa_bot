"""
Store definitions used in rasa actions (e.g., related to database).
"""

import pandas as pd

DATABASE_HOST = "mysql"
DATABASE_PASSWORD = "password"
DATABASE_PORT = 3306
DATABASE_USER = "root"


# List of activities
df_act = pd.read_excel("PMT_actions_2023_03_24.xlsx", 
                       converters={'Number': int, 'Construct':str, 'Gender':str, 'Age':int, 'User input':bool,'Content':str})
# Turn columns into lists
df_act["Content"] = [list(df_act.iloc[i]["Content"].split("|")) if not pd.isna(df_act.iloc[i]["Content"]) else [] for i in range(len(df_act))]
