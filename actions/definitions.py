"""
Store definitions used in rasa actions (e.g., related to database).
"""

import pandas as pd
import configparser

config = configparser.ConfigParser()
config.read("config.ini")

DATABASE_HOST = config.get('Credentials', 'host')
DATABASE_PASSWORD = config.get('Credentials', 'password')
DATABASE_PORT = config.getint('Credentials', 'port')
DATABASE_USER = config.get('Credentials', 'user')


# List of activities
df_act = pd.read_excel("PMT_actions_2023_05_24.xlsx", 
                       converters={'Number': float, 'Construct':str, 'Gender':str, 'Age':int, 'User input':bool, 'Media':str, 'Content':str, 'Alternative Content': str})
# Turn columns into lists
df_act["Content"] = [list(df_act.iloc[i]["Content"].split("|")) if not pd.isna(df_act.iloc[i]["Content"]) else [] for i in range(len(df_act))]

