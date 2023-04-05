# This files contains your custom actions which can be used to run
# custom Python code.
#
# See this guide on how to implement these action:
# https://rasa.com/docs/rasa/custom-actions


from datetime import datetime
from definitions import (ACTIVITY_CLUSTERS, 
                         DATABASE_HOST, DATABASE_PASSWORD, 
                         DATABASE_PORT, DATABASE_USER, df_act,
                         NUM_ACTIVITIES)
from rasa_sdk import Action, FormValidationAction, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import FollowupAction, SlotSet
from typing import Any, Dict, List, Optional, Text

import logging
import mysql.connector


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
    

class ActionSaveActivityExperience(Action):
    def name(self):
        return "action_save_activity_experience"

    async def run(self, dispatcher: CollectingDispatcher,
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
        
        slots_to_save = ["effort", "activity_experience_slot",
                         "activity_experience_mod_slot",
                         "dropout_response"]
        for slot in slots_to_save:
        
            save_sessiondata_entry(cur, conn, prolific_id, session_num,
                                   slot, tracker.get_slot(slot),
                                   formatted_date)

        conn.close()
    
    
def save_sessiondata_entry(cur, conn, prolific_id, session_num, response_type,
                           response_value, time):
    query = "INSERT INTO sessiondata(prolific_id, session_num, response_type, response_value, time) VALUES(%s, %s, %s, %s, %s)"
    cur.execute(query, [prolific_id, session_num, response_type,
                        response_value, time])
    conn.commit()
    

class ActionSaveSession(Action):
    def name(self):
        return "action_save_session"

    async def run(self, dispatcher: CollectingDispatcher,
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
        
        slots_to_save = ["mood", "state_V", "state_S","state_RE", "state_SE", "user_gender"]
        for slot in slots_to_save:
        
            save_sessiondata_entry(cur, conn, prolific_id, session_num,
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
    

class ValidateActivityExperienceModForm(FormValidationAction):
    def name(self) -> Text:
        return 'validate_activity_experience_mod_form'

    def validate_activity_experience_mod_slot(
            self, value: Text, dispatcher: CollectingDispatcher,
            tracker: Tracker, domain: Dict[Text, Any]) -> Dict[Text, Any]:
        # pylint: disable=unused-argument
        """Validate activity_experience_mod_slot input."""
        last_utterance = get_latest_bot_utterance(tracker.events)

        if last_utterance != 'utter_ask_activity_experience_mod_slot':
            return {"activity_experience_mod_slot": None}

        # people should either type "none" or say a bit more
        if not (len(value) >= 5 or "none" in value.lower()):
            dispatcher.utter_message(response="utter_provide_more_detail")
            return {"activity_experience_mod_slot": None}

        return {"activity_experience_mod_slot": value}


def get_previous_activity_indices_from_db(prolific_id):
    
    conn = mysql.connector.connect(
        user=DATABASE_USER,
        password=DATABASE_PASSWORD,
        host=DATABASE_HOST,
        port=DATABASE_PORT,
        database='db'
    )
    cur = conn.cursor(prepared=True)
    
    # get previous activity index from db
    query = ("SELECT response_value FROM sessiondata WHERE prolific_id = %s and response_type = %s")
    cur.execute(query, [prolific_id, "activity_new_index"])
    result = cur.fetchall()
    
    # So far, we have sth. like [('49',), ('44',)]
    result = [i[0] for i in result]
    
    conn.close()
    
    return result


def get_activity_cluster_counts_from_db():
    "Compute how many times each activity cluster has already been chosen."

    conn = mysql.connector.connect(
        user=DATABASE_USER,
        password=DATABASE_PASSWORD,
        host=DATABASE_HOST,
        port=DATABASE_PORT,
        database='db'
    )
    cur = conn.cursor(prepared=True)
    
    # Get cluster indices from database
    query = ("SELECT response_value FROM sessiondata WHERE response_type = %s")
    cur.execute(query, ["cluster_new_index"])
    result = cur.fetchall()
    
    cluster_indices = [int(i[0]) for i in result]
    
    #logging.info("Cluster indices db:" + str(cluster_indices))
    
    cluster_counts = [cluster_indices.count(i) for i in ACTIVITY_CLUSTERS]
    
    return cluster_counts


def get_activity_counts_from_db():
    "Compute how many times each activity has already been chosen."

    conn = mysql.connector.connect(
        user=DATABASE_USER,
        password=DATABASE_PASSWORD,
        host=DATABASE_HOST,
        port=DATABASE_PORT,
        database='db'
    )
    cur = conn.cursor(prepared=True)
    
    # Get cluster indices from database
    query = ("SELECT response_value FROM sessiondata WHERE response_type = %s")
    cur.execute(query, ["activity_new_index"])
    result = cur.fetchall()
    
    activity_indices = [int(i[0]) for i in result]
    
    #logging.info("Activity indices db:" + str(activity_indices))
    
    activity_counts = [activity_indices.count(i) for i in range(0, NUM_ACTIVITIES)]
    
    return activity_counts

    
class ActionChooseActivity(Action):

    def name(self) -> Text:
        return "action_choose_activity"

    def run(self, dispatcher, tracker, domain):

        prolific_id = tracker.current_state()['sender_id']
        user_age = tracker.get_slot("session_num")
        user_gender = tracker.get_slot("user_gender")
        state_SE = tracker.get_slot("state_SE")
        
        # get indices of previously assigned activities
        # this returns a list of strings
        curr_act_ind_list = get_previous_activity_indices_from_db(prolific_id)
        
        if curr_act_ind_list is None:
            curr_act_ind_list = []
            
        #logging.info("previous activities:" + str(curr_act_ind_list))
        
        # check excluded activities for previously assigned activities
        excluded = []
        for i in curr_act_ind_list:
            excluded += df_act.loc[int(i), 'Exclusion']
            
        logging.info("excluded based on previous: " + str(excluded))
            
        # get eligible activities (not done before and not excluded)
        remaining_indices = [i for i in range(NUM_ACTIVITIES) if not str(i) in curr_act_ind_list and not str(i) in excluded]

        logging.info(remaining_indices)

        # [TODO: add algorithm to decide which activity is selected]

        logging.info(str(df_act.loc[0,"Content"]))

        # [TODO: text formatting of the text]

        msg = str(df_act.loc[0,"Content"])

        dispatcher.utter_message(text=msg)
        dispatcher.utter_message(text=user_age)
        dispatcher.utter_message(text=state_SE)
        dispatcher.utter_message(text=user_gender)

        
        return []
    