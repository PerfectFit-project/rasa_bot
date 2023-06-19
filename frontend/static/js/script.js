// ========================== start session ========================
$(document).ready(function () {

	//get user ID
	const queryString = window.location.search;
    const urlParams = new URLSearchParams(queryString);
    const userid = urlParams.get('userid');
	user_id = userid;
	

	// get user age group
	userAgeGroup = urlParams.get('a');

	// get user gender - male: 0 and female: 1
	userGender = urlParams.get('g');

		// Make fullscreen
		if ($('.widget').width() == 350) {
			$('.widget').css("width" , "98%");
			$('.widget').css("height" , "100%");
		} else {
			$('.widget').css("width" , "350px");
			$('.widget').css("height" , "100%");
		}
	
	
	//start a session
	send('/start_session1{"age_group":' + userAgeGroup + ',"gender":' + userGender + '}');
})

//=====================================	user enter or sends the message =====================
$(".usrInput").on("keyup keypress", function (e) {
	var keyCode = e.keyCode || e.which;

	var text = $(".usrInput").val();
	if (keyCode === 13) {

		if (text == "" || $.trim(text) == "") {
			e.preventDefault();
			return false;
		} else {

			$("#paginated_cards").remove();
			$(".suggestions").remove();
			$(".usrInput").blur();
			setUserResponse(text);
			send(text);
			e.preventDefault();
			return false;
		}
	}
});

$("#sendButton").on("click", function (e) {
	var text = $(".usrInput").val();
	if (text == "" || $.trim(text) == "") {
		e.preventDefault();
		return false;
	}
	else {
		
		$(".suggestions").remove();
		$("#paginated_cards").remove();
		$(".usrInput").blur();
		setUserResponse(text);
		send(text);
		e.preventDefault();
		return false;
	}
})

//==================================== Set user response =====================================
function setUserResponse(message) {
	var UserResponse = '<img class="userAvatar" src=' + "/img/user_picture.png" + '><p class="userMsg">' + message + ' </p><div class="clearfix"></div>';
	$(UserResponse).appendTo(".chats").show("slow");

	$(".usrInput").val("");
	scrollToBottomOfResults();
	showBotTyping();
	$(".suggestions").remove();
}

//=========== Scroll to the bottom of the chats after new message has been added to chat ======
function scrollToBottomOfResults() {

	var terminalResultsDiv = document.getElementById("chats");
	terminalResultsDiv.scrollTop = terminalResultsDiv.scrollHeight;
}

//============== send the user message to rasa server =============================================
function send(message) {
	var url = document.location.protocol + "//" + document.location.hostname;
	$.ajax({

		//url: "http://localhost:5005/webhooks/rest/webhook",		// only for testing
		url: "http://34.175.153.111:5005/webhooks/rest/webhook",		//enable this on production
		type: "POST",
		contentType: "application/json",
		data: JSON.stringify({ message: message, sender: user_id }),
		success: function (botResponse, status) {
			console.log("Response from Rasa: ", botResponse, "\nStatus: ", status);

			setBotResponse(botResponse);

		},
		error: function (xhr, textStatus, errorThrown) {

			// if there is no response from rasa server
			setBotResponse("");
			console.log("Error from bot end: ", textStatus);
		}
	});
}

//=================== set bot response in the chats ===========================================
function setBotResponse(response) {

	$('.usrInput').attr("disabled", true); //To disable the chatbox
	$(".usrInput").prop('placeholder', "Wait for Sam's response."); //The message visible for the user
	//display bot response after the number of miliseconds caputred by the variable 'delay_first_message'
	var delay_first_message = 500;
	if (response.length >=1) {
		delay_first_message = Math.min(Math.max(response[0].text.length * 45, 800), 5000);
	}
	setTimeout(function () {
		hideBotTyping();
		if (response.length < 1) {
			//if there is no response from Rasa, send  fallback message to the user
			var fallbackMsg = "I am facing some issues, please try again later!!!";

			var BotResponse = '<img class="botAvatar" src="/img/chatbot_picture.png"/><p class="botMsg">' + fallbackMsg + '</p><div class="clearfix"></div>';

			$(BotResponse).appendTo(".chats").hide().fadeIn(1000);
			scrollToBottomOfResults();
		}
		//if we get response from Rasa
		else {
			//check if the response contains "text"
			if (response[0].hasOwnProperty("text")) {
				var response_text = response[0].text.split("\n")
				for (j = 0; j < response_text.length; j++){
					var BotResponse = '<img class="botAvatar" src="/img/chatbot_picture.png"/><p class="botMsg">' + response_text[j] + '</p><div class="clearfix"></div>';
					$(BotResponse).appendTo(".chats").hide().fadeIn(1000);
				}
			}

			//check if the response contains "buttons" 
			if (response[0].hasOwnProperty("buttons")) {
				addSuggestion(response[0].buttons);
			}

		scrollToBottomOfResults();
		}
	}, delay_first_message);
	

	//if there is more than 1 message from the bot
	if (response.length > 1){
		//show typing symbol again
		var delay_typing = 600 + delay_first_message;
		setTimeout(function () {
		showBotTyping();
		}, delay_typing)
		
		//send remaining bot messages if there are more than 1
		var summed_timeout = delay_typing;
		for (var i = 1; i < response.length; i++){
			
			//Add delay based on the length of the next message
			summed_timeout += Math.min(Math.max(response[i].text.length * 45, 800), 5000);
			doScaledTimeout(i, response, summed_timeout)
			
		}
	}
	
}


//====================================== Scaled timeout for showing messages from bot =========
// See here for an explanation on timeout functions in javascript: https://stackoverflow.com/questions/5226285/settimeout-in-for-loop-does-not-print-consecutive-values.
function doScaledTimeout(i, response, summed_timeout) {
	
	setTimeout(function() {
		hideBotTyping();
			
		//check if the response contains "text"
		if (response[i].hasOwnProperty("text")) {
			var response_text = response[i].text.split("\n")		
			for (j = 0; j < response_text.length; j++){

				if (response_text[j].includes("youtube")){
					var BotResponse = '<img class="botAvatar" src="/img/chatbot_picture.png"/><iframe class="video" src="' + response_text[j] + '?rel=0" frameborder="0" allow="accelerometer; autoplay; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe><div class="clearfix"></div>';												
				}
				else{
					var BotResponse = '<img class="botAvatar" src="/img/chatbot_picture.png"/><p class="botMsg">' + response_text[j] + '</p><div class="clearfix"></div>';
				}

				if (response_text[j].includes("2 sentences")){
					$('.usrInput').attr("disabled", false); //To disable the chatbox
					$(".usrInput").prop('placeholder', "Type your answer here."); //The message visible for the user
				}
				$(BotResponse).appendTo(".chats").hide().fadeIn(1000);
			}
		}

		//check if the response contains "buttons" 
		if (response[i].hasOwnProperty("buttons")) {
			addSuggestion(response[i].buttons);
		}	


		scrollToBottomOfResults();
		
		if (i < response.length - 1){
			showBotTyping();
		}
	}, summed_timeout);
}


//====================================== Toggle chatbot =======================================
$("#profile_div").click(function () {
	$(".profile_div").toggle();
	$(".widget").toggle();
});


//====================================== Suggestions ===========================================

function addSuggestion(textToAdd) {
	setTimeout(function () {
		$('.usrInput').attr("disabled",true);
		$(".usrInput").prop('placeholder', "Use one of the buttons to answer.");
		var suggestions = textToAdd;
		var suggLength = textToAdd.length;
		$(' <div class="singleCard"> <div class="suggestions"><div class="menu"></div></div></diV>').appendTo(".chats").hide().fadeIn(1000);

		console.log(suggLength)
		if (suggLength <=4){
			// Loop through suggestions
			for (i = 0; i < suggLength; i++) {
				$('<div class="menuChips fourButtons" data-payload=\'' + (suggestions[i].payload) + '\'>' + suggestions[i].title + "</div>").appendTo(".menu");
			}
		}
		else if (suggLength == 11){	// PMT questions buttons
			for (i = 0; i < suggLength; i++) {
				$('<div class="menuChips elevenButtons" data-payload=\'' + (suggestions[i].payload) + '\'>' + suggestions[i].title + "</div>").appendTo(".menu");
			}
		}
		else if (suggLength == 7){	// PMT questions buttons
			for (i = 0; i < suggLength; i++) {
				$('<div class="menuChips sevenButtons" data-payload=\'' + (suggestions[i].payload) + '\'>' + suggestions[i].title + "</div>").appendTo(".menu");
			}
		}
		else{	// mood buttons
			for (i = 0; i < suggLength; i++) {
				$('<div class="menuChips" data-payload=\'' + (suggestions[i].payload) + '\'>' + suggestions[i].title + "</div>").appendTo(".menu");
			}
		}
		scrollToBottomOfResults();
	}, 1000);
}

// on click of suggestions, get the value and send to rasa
$(document).on("click", ".menu .menuChips", function () {
	$('.usrInput').attr("disabled",false);
	$(".usrInput").prop('placeholder', "Type a message...");
	var text = this.innerText;
	var payload = this.getAttribute('data-payload');
	console.log("payload: ", this.getAttribute('data-payload'))
	setUserResponse(text);
	send(payload);

	//delete the suggestions once user click on it
	$(".suggestions").remove();

});


//======================================bot typing animation ======================================
function showBotTyping() {

	var botTyping = '<img class="botAvatar" id="botAvatar" src="/img/chatbot_picture.png"/><div class="botTyping">' + '<div class="bounce1"></div>' + '<div class="bounce2"></div>' + '<div class="bounce3"></div>' + '</div>'
	$(botTyping).appendTo(".chats");
	$('.botTyping').show();
	scrollToBottomOfResults();
}

function hideBotTyping() {
	$('#botAvatar').remove();
	$('.botTyping').remove();
}
