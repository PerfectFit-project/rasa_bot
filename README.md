# PMT chatbot

## Set up a Google Compute Engine environment

See [https://github.com/PerfectFit-project/rasa_example_project#readme]()

## How to run locally and on the Google Compute Engine

1. [Optional: only for the local environment] Create a virtual environment and activate it.
2. Clone the repo to your (virtual) environment.
3. Add the file config.ini under the actions/ directory. **Caution:** This file contains the DB credentials, it should **not be stored anywhere public.**
4. Set your IP address for the correct environment. Go to frontend/static/js/script.js and:

   - If you are using the GCE set:

     ```
     url: "http://<your_instance_IP>:5005/webhooks/rest/webhook"
     ```
   - If you are working on your local environment set:

     ```
     url: "http://localhost:5005/webhooks/rest/webhook"
     ```
5. [Optional] If you want to have a brand new database set, delete the folders **data** and **data_mysql** from your project.
6. From the command line run:

```
docker-compose down --volumes
PASSWORD=[db_password] docker-compose up --build
```

6. [Optional] If you want to retrain the rasa model from the command line run:

   ```
   docker-compose down --volumes

   if [ -e "backend/models" ];then rm -rf "backend/models" ; fi

   cd backend
   rasa train
   wait
   cd ..
   PASSWORD=[db_password] docker-compose up --build

   ```
7. **Access the chatbot:**

   - **Locally** from: http://localhost:3000/?userid=[prolificID_value]&a=[age_group_value]&g=[gender_value]
   - **Online** from: http://34.175.153.111:3000/?userid=[prolificID_value]&a=[age_group_value]&g=[gender_value]
     - [prolificID_value] is the prolificID,
     - [age_group_value] is the user's age group and,
     - [gender_value] is the user's gender where male: 0 and female: 1.

## Database access

To access the db in DBeaver both locally and online:

**Server Host:** localhost (local) and 34.175.153.111 (online)
**Port:** 3306
**Database:** db
**Username:** root
**Password:** [the password shared on Teams]

- Make sure to set "allowPublicKeyRetrieval" to "true" in "Driver properties.

## Dialog flow design

![1687515317902](image/README/1687515317902.png)

* The dialog is split into 4 parts: **Start, PMT & Activity Recommendation, Beliefs & Attitude,** and **End**.
  * **Start:** The user is introduced to the chatbot, and given instructions about how to interact with it. The bot also gathers information about the user's mood.
  * **PMT & Activity Recommendation:** The user is prompted to answer 4 PMT questions. Afterward, an activity is recommended which could involve: reading a text, watching a video, or doing a short mental activity. After that, the user is prompted to reflect on this proposed activity. This process (PMT & Activity Recommendation) is repeated a minimum 1 time and maximum 4 times, as we have 4 PMT constructs. The exact number of iterations is determined by the user's "good state". More on that in the section *Implementation details*. The recommended activity is also computed based on an algorithm explained in the section *Implementation details*.
  * **Beliefs & Attitude:** At the end of the dialog, the user is prompted to answer 5 questions about their beliefs and attitude towards quitting smoking and doing more PA.
  * **End:** The conversation ends with the bot thanking the user and prompting them to click on a prolific link to complete participation.

## Implementation details

The following details refer to the PMT & Activity Recommendation part.

### Number of iterations

The number of iterations of the **4 PMT questions and the recommended activity** is minimum 1 time and maximum 4 times. The exact number of iterations is determined based on the "good state" of the user.

A user is in a "good state" when the score of all PMT questions is over 80%. In particular:

* state_V has values [-5,5] where -5 is the best score
* state_S has values [0,10] where 10 is the best score
* state_RE has values [-5,5] where 5 is the best score
* state_SE has values [0,10] where 10 is the best score.

Hence the algorithm to calculate the "good state" score is:

```
            if ((state_V < -3) and (state_S >= 8) and (state_RE >= 3) and (state_SE >= 8)):
                good_state = True
	    else:
		good_state = False
```

The process **stops** when the user reaches a "good state" score, or when there are 4 iterations, because this is the number of all different PMT constructs.

This method is implemented by **ActionStartPMTQuestions** in the actions.py

### PMT questions

There are 4 PMT constructs and for each, a question is asked. These questions are hardcoded on domain.yml (utter_state_question_PMT_V [-5,5], utter_state_question_PMT_S [0,10], utter_state_question_PMT_RE [-5,5], utter_state_question_PMT_SE [0,10]).

### Activity Recommendation

All recommended activities are taken from an excel file PMT_actions_2023_05_24.xlsx (laterst version), which is found under actions/ directory or on Teams (Resources channel -> Actions folder).

To recommend an activity, we get a list of the activity indices, retrieved from the excel file. This is done at definitions.py. Afterward, we create a personalized list (**getPersonalizedActivitiesList** method) and then we select an activity through **ActionChooseActivity** method.

#### Excel file structure

* **Number**: the index of the activity. This has a value of [1,30]. In some cases, values are not present, because we removed the activity but did not reindex the rest (as it would cause a lot of trouble in the already existing implementation). Actions with an index of integer value (i.e. 1) are considered "parent" actions, while actions with an index of float value (i.e. 1.1, 1.2 etc) are considered "children" actions. More details about this logic on [Types of Activities](#types-of-activities).
* **Construct**: a label that has values [Severity, Vulnerabilty, Self-efficacy, Response-efficacy]
* **Title**: a title of the activity, not used anywhere in the implementation.
* **Gender**: a label assigned to the acitivites, if they are more relevant for a particular gender. Values can be [male, female]. If empty, then it is suitable for all genders.
* **Age**: a label assigned to the acitivites, if they are more relevant for a particular age group. Values can be [39, 49, 59, 60] because we have 4 age groups: <39, 40-49, 50-59, 60 >. If empty, then it is suitable for all ages.
* **Media**: a label that has values [text, video, activity]
* **Content**: the text shown to the user. **Caution:** every time there is a new line, this is converted into a new block of utterance. For "parent" activities, whenever there is a question with possible choices (buttons), the choices (text) is split by ;
* **Source content**: the url or refererance from where the activity is taken from
* **Inspiration**: the url or refererance from where the activity is inspired from

#### Personalization

* To personalize the list we take into account the gender and age group of the user (provided by the url parameters **a** and **g**).
* Using the **getPersonalizedActivitiesList** method from actions.py,  activities that do **not** match with the user's gender are removed.
* Similarly, activities designed for different age-groups (<39, 40-49, 50-59, 60 >), are removed in the same function.
* The **getPersonalizedActivitiesList** method returns a list (**personal_act_df**) with activity indices personalized to the user.

#### Selection of activity

Once we have a **personalized list** of activities indices, we implement the following on **ActionChooseActivity** method:

* Get a list of previously done activities from the user through the **get_user_activity_history** method.
* Get a list of previously done activities from **all users** through the **get_all_users_activity_history** method.
* Using the **get_all_users_activity_history,** we compute the **least frequent PMT construct** through the **random_action_selection** method. If there are more than 1 least frequent, we randomly choose one of them. This method returns the variable **chosen_label** which has as value one of the constuct labels [S, V, RE, SE].
* Given the **random_action_selected, the user's history list and the user's personalized list ,** we use the **random_item_selection** method, to get the **least used activity,** that has the **chosen_label** and the user **has not done before.** The method returns an activity index (**chosen_activity_index**).

#### Types of Activities

There are 3 media of activities: text, video, activity (as described in the [Excel file structure](#excel-file-structure)).

* If an activity is of media "video" or "activity", then the **ActionVidActActivity** method is called and the content is shown. For this media, there are only "parent" actions. The **chosen_activity_index** slot is set to the index of this parent action.
* If an activity is of media "text", then there is some interaction with the user. For example, the user might be asked "How many deaths are caused by lung cancer per year?", and there are suggested buttons that the user selects.

  For that purpose, there are parent activities (i.e. 1 that include the question and the buttons) and children activities (i.e 1.1, 1.2 etc that include the main text content).

  * After uttering the parent's activity content (i.e. 1) with the **ActionTextActivity** method, and receiving the user's answer, the **ActionUserInput** method is called, to utter the child's activity content (i.e. 1.1).
  * Unlike with videos and activities, the **chosen_activity_index** slot is set to the index of the child action, and the **user_input** slot is set to the index of the parent action.
  * There is an exception for activities with index 1 and 24 where the bot's utterance depends on the user's answer (see **activityIsUserConditional** method).
  * Similarly, for activities with index 3,5,16,29 the bot's utterance depends on the user's answer (see **ActionUserInput** method).
* At the end, in all media (text, video, activity) the user is prompted to reflect or type in their thoughts of the recommended activity. For that the bot utters 3 alternatives set to the **utter_ask_user_input_activity_slot** slot.
* If the user's answer is too short (configured to be minimum 40 characters) the user is asked to expand on their answer. The validation is implemented with the **validate_user_input_activity_slot** method.

### Database structure

There are 2 tables:

* **sessiondata** with columns:

| Columns | prolific_id  | round_num | response_type                                                                                                                                                                                                       | response_value    | time |
| ------- | ------------ | --------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------- | ---- |
| Values  | [prolificID] | [1-4]     | [mood,<br /> state_V, <br />state_S, <br />state_SE, <br />state_RE, <br />intention_using_PA,<br />attitude_using_PA,<br />intention_quitting_smoking,<br />intention_doing_more_PA,<br />intention_exploring_PA] | (see table below) |      |

| response_type              | response_value      | Comments                                                                                                                                                                                                       |
| -------------------------- | ------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| mood                       | ["happy","sad"....] | -                                                                                                                                                                                                              |
| state_V                    | [-5,5]              | On a scale from -5 to 5, how likely do you think it is that you will overall experience harmful or helpful consequences as a result of long-term smoking?<br />-5: Very likely harmful, 5: Very likely helpful |
| state_S                    | [0,10]              | On a scale from 0 to 10, how severe do you think are any harmful consequences of long-term smoking?<br />0: Very severe threat, 10: Very severe threat                                                        |
| state_RE                   | [-5,5]              | On a scale from -5 to 5, how do you think becoming more physically active affects quitting smoking?<br />-5: Makes it a lot harder, 5: Makes it a lot easier                                                  |
| state_SE                   | [0,10]              | On a scale from 0 to 10, how confident are you that you can become more physically active?<br />0: Not at all confident, 10: Completely confident                                                              |
| intention_using_PA         | [0,10]              | If you quit smoking, how likely are you to use physical activity to help you?-<br />0: Very unlikely, 10: Very likely                                                                                          |
| attitude_using_PA          | [-5,5]              | How harmful or helpful do you regard physical activity when it comes to quitting smoking?<br />-5: Very likely harmful, 5: Very likely helpful                                                                 |
| intention_quitting_smoking | [0,10]              | How likely are you to quit smoking in the next 6 months?<br />0: Very unlikely, 10: Very likely                                                                                                                |
| intention_doing_more_PA    | [0,10]              | How likely are you to become more physically active in the next 6 months?<br />0: Very unlikely, 10: Very likely                                                                                               |
| intention_exploring_PA     | [0,10]              | How likely are you to explore physical activity as an aid for quitting smoking?<br />0: Very unlikely, 10: Very likely                                                                                         |

* activity_history with columns:

| Columns | prolific_id  | round_num | activity_index | activity_response                | time |
| ------- | ------------ | --------- | -------------- | -------------------------------- | ---- |
| Values  | [prolificID] | [1-4]     | [1-30]         | [the use's input in text format] |      |

** The activity_index can have integer (i.e. 1) or float values (i.e. 1,1) depending on the index of the activity (if it was a parent or child acitivity).

### Restart/Timeout

**Restart**

* The session is saved in the database once at the end of each iteration (PMT questions + activity recommendation) when the user has submitted their input. This is implemented in the **ActionSaveSession** method.
* The session is also saved at the end of the conversation, where the answers from the beliefs and attitude questions are also saved. This is implemented in the **ActionSaveEndSession** method.
* Due to the above implementation, a user can restart the session (refresh page) before the first iteration. After that, the session is considered invalid. In that case, the user is prompted to contact the researcher.

**Timeout**

* There is a check if the session has been active for too long using the **ActionSessionStart** method.
* Currently **session_expiration_time = 60** (configured in domail.yml), where 60 is the maximum minutes of a session before a timeout. This is because it was estimated that on average the minimum duration of a session ( with one iteration) is approximately 15 minutes.

### Frontend details

#### **Mobile**

To improve the buttons' UI and be responsive on mobile/tablet/deskop the following adaptations are used:

```
.menu {
	padding: 5px;
	display: flex;
	flex-wrap: wrap;
	justify-content: center;
}

.menuChips {
	display: inline-block;
	background: #2c53af;
	color: #fff;
	padding: 5px;
	padding-left: 8px;
	padding-right: 8px;
	margin-left: 2px;
	margin-right: 2px;
	margin-bottom: 5px;
	cursor: pointer;
	border-radius: 15px;
	font-size: 14px;
	box-shadow: 2px 5px 5px 1px #dbdade;
	width: calc(100%/5);
	text-align: center;

}

.fourButtons{
	width: 100% !important;
}

.sevenButtons{
	width: calc(100%/4);
}

.elevenButtons{
	width: unset !important;
	padding: 10px;
}

@media (max-width: 767px) {
	.menuChips {
		width: calc(100%/3);
	}

	.fourButtons{
		width: 100% !important;
	}

	.sevenButtons{
		width: 100% !important;
	}

	.elevenButtons{
		width: 100% !important;
	}
}
```

#### **Videos & Links**

To add videos and links in the bot's utterance adjust the code in the **doScaledTimeout** fuction in script.js

Replace this:

```
var BotResponse = '<img class="botAvatar" src="/img/chatbot_picture.png"/><p class="botMsg">' + response_text[j] + '</p><div class="clearfix"></div>';

```

with the following:

```
if (isYouTubeVideoLink(response_text[j])){
	var BotResponse = '<img class="botAvatar" src="/img/chatbot_picture.png"/><iframe class="video" src="' + response_text[j] + '?rel=0" frameborder="0" allow="accelerometer; autoplay; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe><div class="clearfix"></div>';
}
else if(isWebLink(response_text[j])){
	var BotResponse = '<img class="botAvatar" src="/img/chatbot_picture.png"/><a class="botMsg link" href="' + response_text[j] + '" target="_blank">' + response_text[j] + '</a><div class="clearfix"></div>';
}
else{
	var BotResponse = '<img class="botAvatar" src="/img/chatbot_picture.png"/><p class="botMsg">' + response_text[j] + '</p><div class="clearfix"></div>';
}
```

and add the following functions as well:

```
function isYouTubeVideoLink(url) {
	var embedPattern = /^https:\/\/www\.youtube\.com\/embed\/[a-zA-Z0-9_-]+$/;
	return embedPattern.test(url);
  }
  
function isWebLink(url) {
	var webPattern = /^(https?:\/\/)?([a-zA-Z0-9_-]+\.)*[a-zA-Z0-9_-]+\.[a-zA-Z]{2,}(\/[^\s]*)?$/i;
	return webPattern.test(url);
}
```

#### **Disable user's input when not needed**

To disable the user's input see this code in the **setBotResponse** function in script.js

```
$('.usrInput').attr("disabled", true); //To disable the chatbox
$(".usrInput").prop('placeholder', "Wait for Sam's response.");
```

And to enable the user's input when needed see below (not very elegant code but it works)

```
if (response_text[j].includes("2 sentences")){
	$('.usrInput').attr("disabled", false); //To disable the chatbox
	$(".usrInput").prop('placeholder', "Type your answer here."); //The message visible for the user
}
```
