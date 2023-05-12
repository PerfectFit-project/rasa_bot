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
from rasa_sdk.events import FollowupAction, SlotSet, EventType
from rasa_sdk.types import DomainDict
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
            return [FollowupAction("utter_end_of_session")]
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
    
def showText(dispatcher, item_index):
    text_content = df_act.loc[df_act['Number'] == item_index, 'Content'].values[0]

    for line in text_content:
        dispatcher.utter_message(text=line)   

    return

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
        # delete rows that are of opposite gender
        if (row['Gender'] == 'female' and gender == '0') or (row['Gender'] == 'male' and gender == '1'):     
            df_act_copy.drop(index, inplace=True)

        # delete rows that are of a different age range (50-60 only)
        if (row['Age']) == '50' and (age < 50 or age > 60):     
            df_act_copy.drop(index, inplace=True)

        # delete rows that are of a different age range (40-49 only)
        if (row['Age']) == '40' and (age < 40 or age > 49):     
            df_act_copy.drop(index, inplace=True)

        # delete rows that are of a different age range (39++ only)
        if (row['Age']) == '30' and (age > 39):     
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

    conn.close()
        
    return already_done_activities_indices


def construct_activity_random_selection(personalized_list, history_list):
    # create a dictionary to map the labels to the values
    labels = {}
    for i in range(1, 11):
        labels["S"] = labels.get("S", []) + [i]
    for i in range(11, 19):
        labels["V"] = labels.get("V", []) + [i]
    for i in range(19, 26):
        labels["SE"] = labels.get("SE", []) + [i]
    for i in range(26, 32):
        labels["RE"] = labels.get("RE", []) + [i]

    # merge the two lists and assign labels to each value
    merged = {}
    for val in personalized_list + history_list:
        for key in labels:
            if val in labels[key]:
                merged[val] = key

    # count the frequency of each label
    freq = {}
    for key in labels:
        freq[key] = 0
    for val in merged.values():
        freq[val] += 1

    # randomly choose a label among the least frequent ones
    least_freq = min(freq.values())
    least_freq_labels = [key for key in freq if freq[key] == least_freq]
    chosen_label = random.choice(least_freq_labels)

    # get the possible values for the chosen label
    possible_values = [val for val in merged if merged[val] == chosen_label]
    logging.info("Possible values:" + str(possible_values) )

    return(random.choice(possible_values))


def has_children(activity_chosen_index):
    matches = []

    print(df_act['Number'].to_list())

    for num in df_act['Number'].to_list():
        if int(num) == activity_chosen_index and num != activity_chosen_index:
            matches.append(num)

    if matches:
        selected_sub_activity_index = random.choice(matches)
        return selected_sub_activity_index
    else:
        return activity_chosen_index


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
        query = "INSERT INTO activity_history(prolific_id, round_num, activity_index, activity_response, time) VALUES(?, ?, ?, ?, ?)"
        queryMatch = [prolific_id, 
                      round_num,
                      chosen_activity_index,
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

        age = tracker.get_slot("age")
        gender = tracker.get_slot("gender")
        round_num = tracker.get_slot("round_num")

        prolific_id = tracker.current_state()['sender_id']

        # get a df with personalized activities
        personal_act_df = getPersonalizedActivitiesList(age, gender)

        # get list of indices of personalized activities and get all the main items. This can be [1,2,3]
        personal_act_ind_list = [int(x) for x in personal_act_df['Number'] if int(x) == x]     
        logging.info("Personalized activity list:" + str(personal_act_ind_list)) 

        # get list of indices of previously done activities. This can be [1.3, 4, 5.1]
        history_activities_list = get_user_activity_history(prolific_id)

        # get the main items of the history list. So we have [1, 4, 5]
        history_activities_list = [int(x) for x in history_activities_list if int(x) == x]
        logging.info("History activity list:" + str(history_activities_list))

        # get a randlomly chosen activity, among the least selected construct so far
        chosen_activity_index = construct_activity_random_selection(personal_act_ind_list, history_activities_list)
        logging.info("Chosen activity index: " + str(personal_act_df.loc[personal_act_df['Number'] == chosen_activity_index, 'Number'].values[0]))
        
        #chosen_activity_index = 6            # only for testing, remove on production

        # get the activity's type of media
        chosen_activity_media = str(personal_act_df.loc[personal_act_df['Number'] == chosen_activity_index, 'Media'].values[0])

        # check if the activity has children, if not return the same index, else randomly choose and return a child activity
        chosen_activity_child_index = has_children(chosen_activity_index)
        logging.info("Chosen activity child index: " + str(chosen_activity_child_index))

        # the chosen activity doesn't have children, so it's only activity or video
        logging.info("Chosen activity index: " + str(chosen_activity_index))
        if chosen_activity_child_index == chosen_activity_index:
        
            saveActivityToDB(prolific_id, round_num, chosen_activity_index)

            logging.info(chosen_activity_media + " action")
            return[SlotSet("chosen_activity_index", float(chosen_activity_index)), 
                    SlotSet("chosen_activity_media", chosen_activity_media),
                    FollowupAction("action_vid_act_activity")]  
            
        # the chosen activity has children, so it's a text
        # we reverse chosen_activity_index slot with the child's activity index
        # because we need to assign to user_input the parent's activity index
        else: 
            return [SlotSet("chosen_activity_index", float(chosen_activity_child_index)), 
                    SlotSet("user_input", float(chosen_activity_index)),
                    SlotSet("chosen_activity_media", chosen_activity_media),
                    FollowupAction("action_text_activity")]

class ActionTextActivity(Action):

    def name(self) -> Text:
        return "action_text_activity"

    def run(self, dispatcher: CollectingDispatcher,
                tracker: Tracker,
                domain: DomainDict) -> List[EventType]:

        user_input = tracker.get_slot("user_input")
        logging.info("ActionTextActivity act_index:"+ str(user_input))

        text_content = df_act.loc[df_act['Number'] == user_input, 'Content'].values[0]

        text_content_split = text_content[0].split("\n")

        buttons = []
        for answer in text_content_split[2].split(";"):
                logging.info("Button:" + answer)
                btn = {"title":' ' + answer + ' ', "payload": '/user_input{"u_input":"'+ answer +'"}'}
                buttons.append(btn)

        
        dispatcher.utter_message(text=text_content_split[0],buttons=buttons)

        return []

class ActionVidActActivity(Action):   

    def name(self) -> Text:
        return "action_vid_act_activity"

    def run(self, dispatcher, tracker, domain):

        chosen_activity_index = tracker.get_slot("chosen_activity_index")
        logging.info("ActionVidActActivity act_index:"+ str(chosen_activity_index))
        
        showText(dispatcher, chosen_activity_index)

        return []


def activityIsOne(tracker):
    if (tracker.get_slot("u_input") == "physical health"):
        chosen_activity_index = 1.1
    elif (tracker.get_slot("u_input") == "heart diseases"):
        chosen_activity_index = 1.2
    elif (tracker.get_slot("u_input") == "appearance"):
        chosen_activity_index = 1.3
    elif (tracker.get_slot("u_input") == "oral health"):
        chosen_activity_index = 1.4
    elif (tracker.get_slot("u_input") == "respiratory illnesses"):
        chosen_activity_index = 1.5
    elif (tracker.get_slot("u_input") == "life expectancy"):
        chosen_activity_index = 1.6
    elif (tracker.get_slot("u_input") == "fertility"):
        chosen_activity_index = 1.7

    return chosen_activity_index


class ActionUserInput(Action):

    def name(self) -> Text:
        return "action_user_input"
    
    def run(self, dispatcher, tracker, domain):

        prolific_id = tracker.current_state()['sender_id']
        round_num = tracker.get_slot("round_num")

        # in case of action no.1, the text is dependent on the user's answer
        if (tracker.get_slot("user_input") == 1):
            chosen_activity_index = activityIsOne(tracker)
        else: chosen_activity_index = tracker.get_slot("chosen_activity_index")


        logging.info("ActionUserInput chosen_activity_index: "+ str(chosen_activity_index))

        showText(dispatcher, chosen_activity_index)
        saveActivityToDB(prolific_id, round_num, chosen_activity_index)

        return []
    


class ValidateUserInputActivityForm(FormValidationAction):
    def name(self) -> Text:
        return 'validate_user_input_activity_form'

    def validate_user_input_activity_slot(
            self, value: Text, dispatcher: CollectingDispatcher,
            tracker: Tracker, domain: Dict[Text, Any]) -> Dict[Text, Any]:
        # pylint: disable=unused-argument
        """Validate user_input_activity_slot input."""
        last_utterance = get_latest_bot_utterance(tracker.events)
        last_user_message = tracker.latest_message.get('text')

        if last_utterance != 'utter_ask_user_input_activity_slot':
            return {"user_input_activity_slot": None}

        # require the user to enter at least 200 chars
        #if not len(last_user_message) >= 200:      # uncomment on production
        if not len(last_user_message) >= 1:         # only for testing, remove on production
            dispatcher.utter_message(response="utter_longer_answer_activity")
            return {"user_input_activity_slot": None}

        return {"user_input_activity_slot": value}
