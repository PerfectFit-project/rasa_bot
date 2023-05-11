# PMT chatbot

## Implementation details

* Access the chatbot from http://localhost:3000/?userid=70&sessionid=1&a=3&g=4 where userid=`<value>` is an id given from prolific, a=`<value> is the user's age and g=<value> is the user's gender where male: 0 and female: 1.`
* ![Alt text](Chatbot dialog flow.jpg?raw=true "Chatbot Dialog Flow")
* The bot is configured to ask the PMT questions and recommend activities 2 times. This is hardcoded in ActionStartPMTQuestions action, in actions.py
* For each PMT question, the user's answer is saved to the sessiondata table. Since we have only one session here, session_num=1 for all. Each round is distinguised with the round_num column.

### Personalization

* The bot takes into account the gender and age of the user.
* Using the getPersonalizedActivitiesList method from actions.py, we remove activities that do not match with the user's profile.
* The getPersonalizedActivitiesList method splits the users in age-groups of: <39 , 40-49, 50-60, and 60 > years old.

### Selection of activity

* This is done though construct_activity_random_selection method. Warning! the actions category is hardcoded according to their number.
* Through a (kinda) complicated algorithm the selection of activitity goes as follows:
  * We take into account the user's history activity, and the list of activities the user could possibly do.
  * We merge the 2 lists, and count their frequency of occurance.
  * Then, based on their PMT label, we choose the least frequent activity.

### Activities

There are 3 types of activities: text, video, activity (which can be found in the excel). 

* If an activity is "text", then we have included some interaction with the user. For that purpose, we have parent activities (i.e. 1 ) and child activities (i.e 1.1, 1.2 etc).
  * After uttering the parent's activity content, and receiving the user's answer (which is not stored anywhere, or we don't care about it), the ActionTextActivity action is called, to utter the child's activity content.
  * Except for activity no.1 where the bot's utterance depends on the user's answer (see activityIsOne method).
  * In all "text" activities, the user_input has value to "True" to indicate that interaction between user and bot will happen.
* If an acitivity is a "video" or an "activity", there are no child activities here.
  * Both of these follow the same behaviour using the ActionVidActActivity action.
  * After the bot utters the main action's content,  the user is expected to respond, and the asnwer is saved to the db.
