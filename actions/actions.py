# This files contains your custom actions which can be used to run
# custom Python code.
#
# See this guide on how to implement these action:
# https://rasa.com/docs/rasa/custom-actions


from datetime import datetime
from definitions import (DATABASE_HOST, DATABASE_PASSWORD, 
                         DATABASE_PORT, DATABASE_USER, df_act)
from rasa_sdk import Action, FormValidationAction, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import FollowupAction, SlotSet
from typing import Any, Dict, List, Optional, Text

import logging
import mysql.connector
import random

class ActionEndDialog(Action):
    """Action to cleanly terminate the dialog."""
    # ATM this action just call the default restart action
    # but this can be used to perform actions that might be needed
    # at the end of each dialog
    def name(self):
        return "action_end_dialog"

    async def run(self, dispatcher, tracker, domain):

        return [FollowupAction('action_restart')]
    

class ActionDefaultFallbackEndDialog(Action):
    """Executes the fallback action and goes back to the previous state
    of the dialogue"""

    def name(self) -> Text:
        return "action_default_fallback_end_dialog"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        dispatcher.utter_message(template="utter_default")
        dispatcher.utter_message(template="utter_default_close_session")

        # End the dialog, which leads to a restart.
        return [FollowupAction('action_end_dialog')]
    
class ActionStartPMTQuestions(Action):
    """ 
        Start asking the PMT questions and providing an activity to do.
        Repeat the action as many times as defined in the round_num value.
    """
    def name(self) -> Text:
        return "action_start_PMT_questions"

    def run(self, 
            dispatcher: CollectingDispatcher, 
            tracker: Tracker, 
            domain: Dict[Text, Any]
        ) -> List[Dict[Text, Any]]:

        round_num = tracker.get_slot("round_num")
        round_num += 1
        
        if round_num == 3:          # we will have only 2 rounds
            return [FollowupAction("utter_email_reminder")]
        else:
            return [SlotSet("round_num", round_num), FollowupAction("utter_state_question_intro")]



def get_latest_bot_utterance(events) -> Optional[Any]:
    """
       Get the latest utterance sent by the VC.
        Args:
            events: the events list, obtained from tracker.events
        Returns:
            The name of the latest utterance
    """
    events_bot = []

    for event in events:
        if event['event'] == 'bot':
            events_bot.append(event)

    if (len(events_bot) != 0
            and 'metadata' in events_bot[-1]
            and 'utter_action' in events_bot[-1]['metadata']):
        last_utterance = events_bot[-1]['metadata']['utter_action']
    else:
        last_utterance = None

    return last_utterance


def check_session_not_done_before(cur, prolific_id, session_num):
    
    query = ("SELECT * FROM sessiondata WHERE prolific_id = %s and session_num = %s")
    cur.execute(query, [prolific_id, session_num])
    done_before_result = cur.fetchone()
    
    not_done_before = True

    # user has done the session before
    if done_before_result is not None:
        not_done_before = False
        
    return not_done_before
    


class ActionLoadSessionFirst(Action):
    
    def name(self) -> Text:
        return "action_load_session_first"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
    
        prolific_id = tracker.current_state()['sender_id']
        
        conn = mysql.connector.connect(
            user=DATABASE_USER,
            password=DATABASE_PASSWORD,
            host=DATABASE_HOST,
            port=DATABASE_PORT,
            database='db'
        )
        cur = conn.cursor(prepared=True)
        
        session_loaded = check_session_not_done_before(cur, prolific_id, 1)
        
        conn.close()

        return [SlotSet("session_loaded", session_loaded)]


class ActionLoadSessionNotFirst(Action):

    def name(self) -> Text:
        return "action_load_session_not_first"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        prolific_id = tracker.current_state()['sender_id']
        session_num = tracker.get_slot("session_num")
        
        session_loaded = True
        mood_prev = ""
        
        conn = mysql.connector.connect(
            user=DATABASE_USER,
            password=DATABASE_PASSWORD,
            host=DATABASE_HOST,
            port=DATABASE_PORT,
            database='db'
        )
        cur = conn.cursor(prepared=True)
        
        # get user name from database
        query = ("SELECT name FROM users WHERE prolific_id = %s")
        cur.execute(query, [prolific_id])
        user_name_result = cur.fetchone()
        
        if user_name_result is None:
            session_loaded = False
            
        else:
            user_name_result = user_name_result[0]
            
            # check if user has done previous session before '
            # (i.e., if session data is saved from previous session)
            query = ("SELECT * FROM sessiondata WHERE prolific_id = %s and session_num = %s and response_type = %s")
            cur.execute(query, [prolific_id, str(int(session_num) - 1), "state_V"])
            done_previous_result = cur.fetchone()
            
            if done_previous_result is None:
                session_loaded = False
                
            else:
                # check if user has not done this session before
                # checks if some data on this session is already saved in database
                # this basically means that it checks whether the user has already 
                # completed the session part until the dropout question before,
                # since that is when we first save something to the database
                session_loaded = check_session_not_done_before(cur, prolific_id, 
                                                               session_num)
                
                if session_loaded:
                    # Get mood from previous session
                    query = ("SELECT response_value FROM sessiondata WHERE prolific_id = %s and session_num = %s and response_type = %s")
                    cur.execute(query, [prolific_id, str(int(session_num) - 1), "mood"])
                    mood_prev = cur.fetchone()[0]
                    
        
        conn.close()

        
        return [SlotSet("user_name_slot_not_first", user_name_result),
                SlotSet("mood_prev_session", mood_prev),
                SlotSet("session_loaded", session_loaded)]
        
        
    
class ActionSaveNameToDB(Action):

    def name(self) -> Text:
        return "action_save_name_to_db"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        now = datetime.now()
        formatted_date = now.strftime('%Y-%m-%d %H:%M:%S')

        conn = mysql.connector.connect(
            user=DATABASE_USER,
            password=DATABASE_PASSWORD,
            host=DATABASE_HOST,
            port=DATABASE_PORT,
            database='db'
        )
        cur = conn.cursor(prepared=True)
        query = "INSERT INTO users(prolific_id, name, time) VALUES(%s, %s, %s)"
        queryMatch = [tracker.current_state()['sender_id'], 
                      tracker.get_slot("user_name_slot"),
                      formatted_date]
        cur.execute(query, queryMatch)
        conn.commit()
        conn.close()

        return []
    
    
def save_sessiondata_entry(cur, conn, prolific_id, session_num, round_num, response_type,
                           response_value, time):
    query = "INSERT INTO sessiondata(prolific_id, session_num, round_num, response_type, response_value, time) VALUES(%s, %s, %s, %s, %s, %s)"
    cur.execute(query, [prolific_id, session_num, round_num, response_type,
                        response_value, time])
    conn.commit()
    

class ActionSaveSession(Action):
    def name(self):
        return "action_save_session"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        now = datetime.now()
        formatted_date = now.strftime('%Y-%m-%d %H:%M:%S')

        conn = mysql.connector.connect(
            user=DATABASE_USER,
            password=DATABASE_PASSWORD,
            host=DATABASE_HOST,
            port=DATABASE_PORT,
            database='db'
        )
        cur = conn.cursor(prepared=True)
        
        prolific_id = tracker.current_state()['sender_id']
        session_num = tracker.get_slot("session_num")
        round_num = tracker.get_slot("round_num")
        
        slots_to_save = ["mood", "state_V", "state_S","state_RE", "state_SE"]
        for slot in slots_to_save:
            save_sessiondata_entry(cur, conn, prolific_id, session_num, round_num, 
                                   slot, tracker.get_slot(slot),
                                   formatted_date)

        conn.close()
        
        return []
    

class ValidateUserNameForm(FormValidationAction):
    def name(self) -> Text:
        return 'validate_user_name_form'

    def validate_user_name_slot(
            self, value: Text, dispatcher: CollectingDispatcher,
            tracker: Tracker, domain: Dict[Text, Any]) -> Dict[Text, Any]:
        # pylint: disable=unused-argument
        """Validate user_name_slot input."""
        last_utterance = get_latest_bot_utterance(tracker.events)

        if last_utterance != 'utter_ask_user_name_slot':
            return {"user_name_slot": None}

        if not len(value) >= 1:
            dispatcher.utter_message(response="utter_longer_name")
            return {"user_name_slot": None}

        return {"user_name_slot": value}
    

class ValidateActivityExperienceForm(FormValidationAction):
    def name(self) -> Text:
        return 'validate_activity_experience_form'

    def validate_activity_experience_slot(
            self, value: Text, dispatcher: CollectingDispatcher,
            tracker: Tracker, domain: Dict[Text, Any]) -> Dict[Text, Any]:
        # pylint: disable=unused-argument
        """Validate activity_experience_slot input."""
        last_utterance = get_latest_bot_utterance(tracker.events)

        if last_utterance != 'utter_ask_activity_experience_slot':
            return {"activity_experience_slot": None}

        # people should either type "none" or say a bit more
        if not (len(value) >= 10 or "none" in value.lower()):
            dispatcher.utter_message(response="utter_provide_more_detail")
            return {"activity_experience_slot": None}

        return {"activity_experience_slot": value}

def getPersonalizedActivitiesList(age, gender):

    df_act_copy = df_act.copy(True)

    for index, row in df_act_copy.iterrows():
        if (row['Gender'] == 'female' and gender == 'male') or (row['Gender'] == 'male' and gender == 'female'):        # delete rows that are of opposite gender
            df_act_copy.drop(index, inplace=True)

        if (row['Age']) == '50' and (age < 50 or age > 60):     # delete rows that are of a different age range (50-60 only)
            df_act_copy.drop(index, inplace=True)

        if (row['Age']) == '40' and (age < 40 or age > 49):     # delete rows that are of a different age range (40-49 only)
            df_act_copy.drop(index, inplace=True)

        if (row['Age']) == '30' and (age > 39):     # delete rows that are of a different age range (39++ only)
            df_act_copy.drop(index, inplace=True)

    return df_act_copy


def get_user_activity_history(prolific_id):
        
    conn = mysql.connector.connect(
        user=DATABASE_USER,
        password=DATABASE_PASSWORD,
        host=DATABASE_HOST,
        port=DATABASE_PORT,
        database='db'
    )
    cur = conn.cursor(prepared=True)
    
    query = ("SELECT activity_index FROM activity_history WHERE prolific_id = %s")
    cur.execute(query, [prolific_id])
    result = cur.fetchall()

    already_done_activities_indices = [int(i[0]) for i in result]
    
    logging.info("Already done activities indices: " + str(already_done_activities_indices))

    conn.close()
        
    return already_done_activities_indices

def saveActivityToDB(prolific_id, round_num, chosen_activity_index):

        now = datetime.now()
        formatted_date = now.strftime('%Y-%m-%d %H:%M:%S')

        conn = mysql.connector.connect(
            user=DATABASE_USER,
            password=DATABASE_PASSWORD,
            host=DATABASE_HOST,
            port=DATABASE_PORT,
            database='db'
        )

        cur = conn.cursor(prepared=True)
        query = "INSERT INTO activity_history(prolific_id, round_num, activity_index, activity_response, time) VALUES(%s, %s, %s, %s, %s)"
        queryMatch = [prolific_id, 
                      round_num,
                      str(chosen_activity_index),
                      None,
                      formatted_date]
        cur.execute(query, queryMatch)
        conn.commit()
        conn.close()

        return []
    
class ActionChooseActivity(Action):
        
    def name(self) -> Text:
        return "action_choose_activity"

    def run(self, dispatcher, tracker, domain):

        age = 29                # for testing purposes, delete them on production
        gender = "female"
        round_num = tracker.get_slot("round_num")

        prolific_id = tracker.current_state()['sender_id']

        # get a df with personalized activities
        personal_act_df = getPersonalizedActivitiesList(age, gender)

        # get list of indices of personalized activities
        personal_act_ind_list = personal_act_df['Number']

        # get list of indices of previously done activities
        done_activities_list = get_user_activity_history(prolific_id)

        if done_activities_list !=[]:
            # remove already_done_activities from the personalized_list and create a new list with available activities
            logging.info("Select random activity from the newly available activities list")
            personal_act_ind_list = [x for x in personal_act_ind_list if x not in set(done_activities_list)]

        chosen_activity_index = random.choice(personal_act_ind_list)
        chosen_activity_media = str(personal_act_df.loc[ chosen_activity_index,'Media'])

        logging.info("Chosen activity: "+ str(personal_act_df.loc[ chosen_activity_index,'Content']))

        #saveActivityToDB(prolific_id, round_num, chosen_activity_index)
    
        if chosen_activity_media == "text":
            return [SlotSet("chosen_activity_index", float(chosen_activity_index)), 
                    SlotSet("chosen_activity_media", chosen_activity_media),
                    FollowupAction("action_text_activity")]
        elif chosen_activity_media == "video":
            return [SlotSet("chosen_activity_index", float(chosen_activity_index)), 
                    SlotSet("chosen_activity_media", chosen_activity_media),
                    FollowupAction("action_video_activity")]
        else: 
            return [SlotSet("chosen_activity_index", float(chosen_activity_index)), 
                    SlotSet("chosen_activity_media", chosen_activity_media),
                    FollowupAction("action_activity_activity")]
    

class ActionTextActivity(Action):   

    def name(self) -> Text:
        return "action_text_activity"

    def run(self, dispatcher, tracker, domain):

        chosen_activity_index = tracker.get_slot("chosen_activity_index")
        logging.info("ActionTextActivity act_index:"+ str(chosen_activity_index))
        
        text_content = df_act.loc[ chosen_activity_index,'Content'][0].split("\n")

        for line in text_content:
            dispatcher.utter_message(text=line)

        return []

class ActionVideoActivity(Action):   

    def name(self) -> Text:
        return "action_video_activity"

    def run(self, dispatcher, tracker, domain):

        chosen_activity_index = tracker.get_slot("chosen_activity_index")
        logging.info("ActionVideoActivity act_index:"+ str(chosen_activity_index))
        
        text_content = df_act.loc[ chosen_activity_index,'Content'][0].split("\n")

        for line in text_content:
            dispatcher.utter_message(text=line)

        return []

class ActionActivityActivity(Action):   

    def name(self) -> Text:
        return "action_activity_activity"

    def run(self, dispatcher, tracker, domain):

        chosen_activity_index = tracker.get_slot("chosen_activity_index")
        logging.info("ActionActivityActivity act_index:"+ str(chosen_activity_index))
        
        text_content = df_act.loc[ chosen_activity_index,'Content'][0].split("\n")

        for line in text_content:
            dispatcher.utter_message(text=line)

        return []
