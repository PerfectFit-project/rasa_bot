"""
Store definitions used in rasa actions (e.g., related to database).
"""

import pandas as pd

DATABASE_HOST = "mysql"
DATABASE_PASSWORD = "pmt_chatbot_2023"
DATABASE_PORT = 3306
DATABASE_USER = "root"


# List of activities
df_act = pd.read_excel("PMT_actions_2023_05_09.xlsx", 
                       converters={'Number': float, 'Construct':str, 'Gender':str, 'Age':int, 'User input':bool, 'Media':str, 'Content':str, 'Alternative Content': str})
# Turn columns into lists
df_act["Content"] = [list(df_act.iloc[i]["Content"].split("|")) if not pd.isna(df_act.iloc[i]["Content"]) else [] for i in range(len(df_act))]

index_items_list = [int(x) for x in df_act['Number'] if int(x) == x]       # to print all the main items
index_sub_items_list = list(set([x for x in df_act['Number'] if isinstance(x, float)]) - set(index_items_list))
