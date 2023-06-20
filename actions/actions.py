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
from rasa_sdk.events import (FollowupAction, SlotSet, EventType, 
                             ActionExecuted, FollowupAction, 
                             SessionStarted, SlotSet)

from rasa_sdk.types import DomainDict
from typing import Any, Dict, List, Optional, Text
from collections import Counter


import logging
import mysql.connector
import random

history_session_list = []

class ActionSessionStart(Action):
    """
        Starts the session and check if there is a timeout
    """
    def name(self) -> Text:
        return "action_session_start"

    async def run(
      self, dispatcher, tracker: Tracker, domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:

        session_loaded = tracker.get_slot("session_loaded")

        # the session should begin with a `session_started` event
        # in case of a timed-out session, we also need this so that rasa does not
        # continue with uncompleted forms.
        events = [SessionStarted()]

        # New session
        if session_loaded == None:
 
            # an `action_listen` should be added at the end as a user message follows
            events.append(ActionExecuted("action_listen"))

        # timed out session
        else:
            dispatcher.utter_message(template="utter_timeout")
            events.append(FollowupAction('action_end_dialog'))

        return events

class ActionEndDialog(Action):
    """
        Action to cleanly terminate the dialog.
    """
    # ATM this action just call the default restart action
    # but this can be used to perform actions that might be needed
    # at the end of each dialog
    def name(self):
        return "action_end_dialog"

    async def run(self, dispatcher, tracker, domain):

        return [FollowupAction('action_restart')]
    

class ActionDefaultFallbackEndDialog(Action):
    """
        Executes the fallback action and goes back to the 
        previous state of the dialogue
    """

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
        Repeat this minimum 1 time, and maximum 4 times. The exact number of iterations is
        computed based on the 'good state' of the participant. If the PMT values are over
        80% then the participant is in a 'good state'.
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

        if round_num == 1:
            return [SlotSet("round_num", round_num), FollowupAction("utter_state_question_intro")]
        else:
            good_state = False
            good_state_score = int(tracker.get_slot("state_V")) + int(tracker.get_slot("state_S")) + int(tracker.get_slot("state_RE")) + int(tracker.get_slot("state_SE"))
            logging.info("good_state_score:" + str(good_state_score))
            if good_state_score/20 >= 0.8:
                good_state = True
            if (good_state) or round_num > 4:
                return [FollowupAction("utter_intentions_attitude_intro")]
            else:
                return [SlotSet("round_num", round_num), FollowupAction("utter_one_more_time")]



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


def check_session_not_done_before(cur, prolific_id):
    
    query = ("SELECT * FROM sessiondata WHERE prolific_id = %s")
    cur.execute(query, [prolific_id])
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
        
        session_loaded = check_session_not_done_before(cur, prolific_id)
        
        conn.close()

        return [SlotSet("session_loaded", session_loaded)]


class ActionLoadSessionNotFirst(Action):

    def name(self) -> Text:
        return "action_load_session_not_first"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        prolific_id = tracker.current_state()['sender_id']
        
        session_loaded = True
        
        conn = mysql.connector.connect(
            user=DATABASE_USER,
            password=DATABASE_PASSWORD,
            host=DATABASE_HOST,
            port=DATABASE_PORT,
            database='db'
        )
        cur = conn.cursor(prepared=True)
        
            
        # check if user has done previous session before '
        # (i.e., if session data is saved from previous session)
        query = ("SELECT * FROM sessiondata WHERE prolific_id = %s and response_type = %s")
        cur.execute(query, [prolific_id, "state_V"])
        done_previous_result = cur.fetchone()
        
        if done_previous_result is None:
            session_loaded = False
            
        else:
            # check if user has not done this session before
            # checks if some data on this session is already saved in database
            # this basically means that it checks whether the user has already 
            # completed the session part until the dropout question before,
            # since that is when we first save something to the database
            session_loaded = check_session_not_done_before(cur, prolific_id)              
        
        conn.close()

        
        return [SlotSet("session_loaded", session_loaded)]
        
    
def save_sessiondata_entry(cur, conn, prolific_id, round_num, response_type,
                           response_value, time):
    query = "INSERT INTO sessiondata(prolific_id, round_num, response_type, response_value, time) VALUES(%s, %s, %s, %s, %s)"
    cur.execute(query, [prolific_id, round_num, response_type,
                        response_value, time])
    conn.commit()
    

class ActionSaveSession(Action):
    """ 
        Saves the session, after every iteration
        including the answers to the PMT questions
    """
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
        round_num = tracker.get_slot("round_num")
        
        slots_to_save = ["mood", "state_V", "state_S","state_RE", "state_SE"]
        for slot in slots_to_save:
            save_sessiondata_entry(cur, conn, prolific_id, round_num, 
                                   slot, tracker.get_slot(slot),
                                   formatted_date)

        conn.close()
        
        return []
    
class ActionSaveEndSession(Action):
    """ 
        Save the session at the end of the dialog,
        including the beliefs and attitude questions
    """
    def name(self):
        return "action_save_end_session"

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
        round_num = tracker.get_slot("round_num")
        
        slots_to_save = ["intention_using_PA", "attitude_using_PA", "intention_quitting_smoking", "intention_doing_more_PA", "intention_exploring_PA"]
        for slot in slots_to_save:
            save_sessiondata_entry(cur, conn, prolific_id, round_num, 
                                   slot, tracker.get_slot(slot),
                                   formatted_date)

        conn.close()
        
        return []

def getPersonalizedActivitiesList(age_group, gender):
    """ 
        Return a personallized list of activities. 
        Given the activity list from the excel, every item that 
        has different gender and age-group than the user is removed from the list.
    """

    df_act_copy = df_act.copy(True)

    for index, row in df_act_copy.iterrows():
        # delete rows that are of opposite gender
        if (row['Gender'] == 'female' and gender != 1) or (row['Gender'] == 'male' and gender != 0):     
            df_act_copy.drop(index, inplace=True)

        # delete rows that are of a different age range (50-60 only)
        if (row['Age']) == '50' and (age_group != 59):     
            df_act_copy.drop(index, inplace=True)

        # delete rows that are of a different age range (40-49 only)
        if (row['Age']) == '40' and (age_group != 49):     
            df_act_copy.drop(index, inplace=True)

        # delete rows that are of a different age range (39++ only)
        if (row['Age']) == '30' and (age_group != 39):     
            df_act_copy.drop(index, inplace=True)

    return df_act_copy


def get_user_activity_history(prolific_id):
    """
       Return a list of the user's previously done activities from the db
       defined by the prolific_id
    """
        
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


def get_all_users_activity_history():
    """
       Return a list of all users' previously done activities from the db
    """
        
    conn = mysql.connector.connect(
        user=DATABASE_USER,
        password=DATABASE_PASSWORD,
        host=DATABASE_HOST,
        port=DATABASE_PORT,
        database='db'
    )
    cur = conn.cursor(prepared=True)
    
    query = ("SELECT activity_index FROM activity_history")
    cur.execute(query)
    result = cur.fetchall()

    already_done_activities_indices = [int(i[0]) for i in result]

    conn.close()
        
    return already_done_activities_indices


def random_action_selection(all_users_history):
    """
        Assign labels ["S","V","SE","RE"] to the all_users_history list and count the frequency of them.
        Then choose the least frequently used action.
        If there are many, choose randomly.
    """
    
    # Define the labels and their corresponding value ranges
    label_ranges = {'S': range(1, 11), 'V': range(11, 19), 'SE': range(19, 26), 'RE': range(26, 30)}

    # Assign labels to the items in the list
    labels = [next((label for label, value_range in label_ranges.items() if item in value_range), None) for item in all_users_history]

    # Count the frequency of each label
    label_counts = Counter(labels)

    # Get the frequency of the labels
    frequencies = list(label_counts.values())

    # If the history is empty
    if (frequencies == []):
        chosen_label = random.choice(["S","V","SE","RE"])

    # Check if all frequencies are the same
    if len(set(frequencies)) == 1 and len(frequencies) == 4:
        # Randomly choose one of the labels
        chosen_label = random.choice(list(label_ranges.keys()))
    else:
        # Include labels with zero frequency
        all_labels = list(label_ranges.keys())
        label_counts = {label: label_counts[label] if label in label_counts else 0 for label in all_labels}

        min_frequency = min(label_counts.values())
        min_frequency_labels = [label for label, count in label_counts.items() if count == min_frequency]

        # Choose a label randomly if all labels have the same frequency
        chosen_label = random.choice(min_frequency_labels)
    return chosen_label


def random_item_selection(least_frequent_action_selected, personalized_list, user_history_list):
    """
        Create a new list with items that the user can do (personalized_list) but
        has not done before (user_history_list).
        Then, given an action index (least_frequent_action_selected), randomly select one item from that list
    """
    new_p_list = [x for x in personalized_list if x not in user_history_list]

    labels = []
    for value in new_p_list:
        if 1 <= int(value) < 11:
            labels.append("S")
        elif 5 < int(value) < 19:
            labels.append("V")
        elif 10 < int(value) < 26:
            labels.append("SE")
        elif 15 < int(value) <= 30:
            labels.append("RE")
        else:
            labels.append(None)

    # Create a list of values that have the label least_frequent_action_selected
    least_frequent_item_list = [value for value, label in zip(new_p_list, labels) if label == least_frequent_action_selected]

    return(random.choice(least_frequent_item_list))


def has_children(activity_chosen_index):
    """
        Check if an action consists of items (children). 
        If true, return the index of chosen item. 
        If there are many items (children), a random item is chosen.
    """
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


class ActionSaveActivityToDB(Action):
    """ 
        Save the completed activity's index and the user's response 
        to the db (activity_history).
    """

    def name(self) -> Text:
        return "action_save_activity_to_db"

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
        query = "INSERT INTO activity_history(prolific_id, round_num, activity_index, activity_response, time) VALUES(?, ?, ?, ?, ?)"
        queryMatch = [tracker.current_state()['sender_id'], 
                      tracker.get_slot("round_num"),
                      tracker.get_slot("chosen_activity_index"),
                      tracker.get_slot("user_input_activity_slot"),
                      formatted_date]
        cur.execute(query, queryMatch)
        conn.commit()
        conn.close()

        return [FollowupAction("utter_cool")]


class ActionChooseActivity(Action):
    """
        Action that chooses the recommended activity to do.
        Gets the user's personalized list, history and the all users' history
        Computes, and returns the activity index [3, 4], and the activity's type of media.

        If the chosen activity index has chidren [2.1, 2.2] return this item's index, 
        and assign the activity's index to the 'user_input' slot.
    """
        
    def name(self) -> Text:
        return "action_choose_activity"

    def run(self, dispatcher, tracker, domain):

        age_group = tracker.get_slot("age_group")
        gender = tracker.get_slot("gender")

        prolific_id = tracker.current_state()['sender_id']

        # get a df with personalized activities
        personal_act_df = getPersonalizedActivitiesList(age_group, gender)

        # get list of indices of personalized activities and get all the main items. This can be [1.3,2,3]
        personalized_list = [int(x) for x in personal_act_df['Number']]     
        logging.info("Personalized activity list:" + str(personalized_list)) 

        # get list of indices of previously done activities. This can be [1.3, 4, 5.1]
        user_history_list = get_user_activity_history(prolific_id)
        logging.info("User history activity list:" + str(user_history_list))

        all_users_history_list = get_all_users_activity_history()
        logging.info("All users history activity list:" + str(all_users_history_list))

        random_action_selected = random_action_selection(all_users_history_list)
        chosen_activity_index = random_item_selection(random_action_selected, personalized_list, user_history_list)

        logging.info("Chosen activity index: " + str(personal_act_df.loc[personal_act_df['Number'] == chosen_activity_index, 'Number'].values[0]))
        chosen_activity_index = 6           # only for testing, remove on production

        # get the activity's type of media
        chosen_activity_media = str(personal_act_df.loc[personal_act_df['Number'] == chosen_activity_index, 'Media'].values[0])

        # check if the activity has children, if not return the same index, else randomly choose and return a child activity
        chosen_activity_child_index = has_children(chosen_activity_index)
        logging.info("Chosen activity child index: " + str(chosen_activity_child_index))

        # the chosen activity doesn't have children, so it's only activity or video
        logging.info("Chosen activity index: " + str(chosen_activity_index))
        if chosen_activity_child_index == chosen_activity_index:
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
    """
        If the recommended activity is of 'text' media, then the user's input is expected
        If the chosen activity index is [1], then check if it has been selected in the past, 
        and utter different text.
    """

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
        for answer in text_content_split[-1].split(";"):
                logging.info("Button:" + answer)
                btn = {"title":' ' + answer + ' ', "payload": '/user_input{"u_input":"'+ answer +'"}'}
                buttons.append(btn)

        # if the activity 1 has been suggested to the user in the past
        if (tracker.get_slot("user_input") == 1 and 1 in history_session_list):
                dispatcher.utter_message(template="utter_action_one_repeated", buttons=buttons)
        else:
            for line in text_content_split[:-3]:
                dispatcher.utter_message(text=line)

            if text_content_split[-3]:
                dispatcher.utter_message(text=text_content_split[-3], buttons=buttons)
            else:
                dispatcher.utter_message(text=text_content_split[-2], buttons=buttons)
            

        history_session_list.append(user_input)
        return []


class ActionVidActActivity(Action):
    """
        If the recommended activity is of 'video' media, 
        then show the video.
    """

    def name(self) -> Text:
        return "action_vid_act_activity"

    def run(self, dispatcher, tracker, domain):

        chosen_activity_index = tracker.get_slot("chosen_activity_index")
        logging.info("ActionVidActActivity act_index:"+ str(chosen_activity_index))
        
        showText(dispatcher, chosen_activity_index)
        history_session_list.append(chosen_activity_index)

        return []


def activityIsUserConditional(tracker):
    """
    If the chosen action index is [1] or [24], return the chidren-items of it.
    """
    if (tracker.get_slot("u_input") == "Physical health"):
        chosen_activity_index = 1.1
    elif (tracker.get_slot("u_input") == "Heart diseases"):
        chosen_activity_index = 1.2
    elif (tracker.get_slot("u_input") == "Appearance"):
        chosen_activity_index = 1.3
    elif (tracker.get_slot("u_input") == "Oral health"):
        chosen_activity_index = 1.4
    elif (tracker.get_slot("u_input") == "Respiratory illnesses"):
        chosen_activity_index = 1.5
    elif (tracker.get_slot("u_input") == "Life expectancy"):
        chosen_activity_index = 1.6
    elif (tracker.get_slot("u_input") == "Fertility"):
        chosen_activity_index = 1.7        
    elif (tracker.get_slot("u_input") == "running" or tracker.get_slot("u_input") == "cycling"):
        chosen_activity_index = 24.1
    elif (tracker.get_slot("u_input") == "home-workout"):
        chosen_activity_index = 24.2
    elif (tracker.get_slot("u_input") == "other" or tracker.get_slot("u_input") == "I don't know"):
        chosen_activity_index = 24.3

    return chosen_activity_index


class ActionUserInput(Action):
    """
        Action called when the recommended activity has chidren.
        In case the recommended action is [1] or [24], 
        call activityIsUserConditional to show custom buttons
    """

    def name(self) -> Text:
        return "action_user_input"
    
    def run(self, dispatcher, tracker, domain):

        # in case of action no.1, the text is dependent on the user's answer
        if (tracker.get_slot("user_input") == 1 or tracker.get_slot("user_input") == 24):
            chosen_activity_index = activityIsUserConditional(tracker) 
        else: chosen_activity_index = tracker.get_slot("chosen_activity_index")

        logging.info("ActionUserInput chosen_activity_index: "+ str(chosen_activity_index))

        showText(dispatcher, chosen_activity_index)
        return []
    


class ValidateUserInputActivityForm(FormValidationAction):
    """
        Validation form to validate the user's input.
        The user is required to input minimum 40 characters, or else
        the bot utters to provide a longer answer.
    """
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
        if not (len(value) >= 40 or "none" in value.lower()):
            dispatcher.utter_message(response="utter_longer_answer_activity")
            return {"user_input_activity_slot": None}

        return {"user_input_activity_slot": value}
