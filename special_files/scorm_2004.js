/*
 * IEngine4
 * IEngine4 Video Engine
 *
 * Copyright (c) Inspired eLearning Inc. 2003-2014.  All Rights Reserved.
 * This source file is proprietary property of Inspired eLearning Inc.
 * http://http://www.inspiredelearning.com/inspired/License
 *
 * @version 4.8.30
 */

//http://scorm.com/scorm-explained/technical-scorm/run-time/run-time-reference/

_2004Debug = false;  // set this to false to turn debugging off
var RECORD_INTERACTIONS = true;
var OVERWRITE_QUESTIONS = true;
var RECORD_SCORE = true;
var RETRY_ATTEMPT = 2;
var ERROR_CODE = "0";

var startTime;
var scoTimer;
var exitPageStatus = false;
var bookmarkSupport = true;
var LastBookmark = "";
var LessonMode = "";
var LessonComplete = false;
var InteractionID = 0;
var ScormInitialized = false;
var CourseRetake = false;
var StudentName = "";
var PreExamInteractionId = 0;
var baseInteractionIdentifier = "interaction-id-000";

var LatestBookmarkPageID = 0;


if (!(typeof (_2004Debug) == "undefined") && _2004Debug === true) {
	WriteToDebug_2004("Showing Interactive Debug Windows");
	ShowDebugWindow_2004();
}
WriteToDebug_2004("----------------------------------------");
WriteToDebug_2004("----------------------------------------");
WriteToDebug_2004("In Start - Version: " + VERSION + "  -- Last Modified=" + window.document.lastModified);
WriteToDebug_2004("Browser Info (" + navigator.appName + " " + navigator.appVersion + ")");
WriteToDebug_2004("URL: " + window.document.location.href);
WriteToDebug_2004("----------------------------------------");
WriteToDebug_2004("----------------------------------------");

function StartCourse_2004(CourseName)
{
	//LastBookmark = "15-17";
	//alert("admin_ReviewMode = " + admin_ReviewMode);
	//admin_ReviewMode = true;
	WriteToDebug_2004("Calling StartCourse_2004 Function");
	WriteToDebug_2004("..Admin_UseSCORM = " + admin_UseScorm + " -- SCORM 2004 = " + admin_UseScorm2004);
	if (admin_UseScorm)
	{
		startTime = new Date();

		WriteToDebug_2004("..Calling LMSInitialize");
		ScormInitialized = SCORM2004_CallInitialize();

		if(ScormInitialized){
			WriteToDebug("..LMS Initialized = " + ScormInitialized);
		}
		else{
			WriteToDebug("..LMS Initialized = " + ScormInitialized);
      		if (SCORM2004_IsAlreadyInitialize()) {
        		WriteToDebug("..LMS is already Initialized");
        		ScormInitialized = true;
      		}
		}

		//if (SCORM2004_IsAlreadyInitialize()) {
		//	WriteToDebug_2004("..LMS is already Initialized");
		//	ScormInitialized = true;
		//}
		//else {
		//	WriteToDebug_2004("..Calling LMSInitialize");
		//	ScormInitialized = SCORM2004_CallInitialize();
		//}

		//console.log( "scorm init status: "+ScormInitialized );
		// uncomment bellow line to start in review mode
		// admin_ReviewMode = true;
		WriteToDebug_2004("..LMS Initialized = " + ScormInitialized);
		if (ScormInitialized)
		{
			LessonMode = SCORM2004_GetLessonMode(); // cmi.mode (“browse”, “normal”, “review”, RO)
			WriteToDebug_2004("..Lesson Mode = " + LessonMode.toString());
			SCORM2004_CallSetValue("cmi.exit", "suspend");
			var status = SCORM2004_GetCompletionStatus(); // cmi.completion_status
			//(“passed”, “completed”, “failed”, “incomplete”, “browsed”, “not attempted”, RW)
			WriteToDebug_2004("..Completion Status = " + status.toString());
			if (status.toLowerCase() == "completed")
			{
				admin_ReviewMode = true;
				WriteToDebug_2004("..Course will run in REVIEW mode");
			}
			else
			{
				SCORM2004_SetInComplete();
				admin_ReviewMode = false;
			}
			var status2 = SCORM2004_CallGetValue("cmi.entry"); //  (“ab-initio”, “resume”, “”, RO) Asserts whether the learner has previously accessed the SCO
			WriteToDebug_2004("..cmi.entry = " + status2.toString());
			if ((status == "not attempted"))
			{
				// the student is now attempting the lesson
				WriteToDebug_2004("..Setting incomplete status");
				SCORM2004_SetInComplete(); // cmi.completion_status
				SCORM2004_SetBookmark(""); // cmi.location
				SCORM2004_SetSuspendData("|"); // cmi.suspend_data
				admin_ReviewMode = false;
			}

			StudentName = SCORM2004_GetStudentName(); // cmi.learner_name
			WriteToDebug_2004("..Student Name = " + StudentName.toString());
			LastBookmark = SCORM2004_GetBookmark(); // cmi.location
			WriteToDebug_2004("..Last Bookmark = " + LastBookmark.toString());
			SuspendData = SCORM2004_GetSuspendData(); // cmi.suspend_data
			SuspendData = String(SuspendData);


//	  console.log('read suspend data:');
//	  console.log(SuspendData);

      //1) load suspend data from LMS
      //2) split string from "|" left side is iEngine, right side belogs to iLMS
      //3) parse left side for iEngine
      //4) set SuspendData variable to be only the right side. Later when saved it will rebuild the left side and prepend it to the SuspendData with "|" as a splitter

			var SuspendDataArrayTemp = SuspendData.split('|');

			if (SuspendDataArrayTemp.length >= 1) {
				if (SuspendDataArrayTemp[0] !== "") {
					var TempSuspendData = JSON.parse(SuspendDataArrayTemp[0]);
					SuspendData = SuspendData.substring(SuspendData.indexOf("|") + 1);

					//load quiz retake number
          var retakeCounterStr = TempSuspendData['Retake'];
					admin_FinalRetakeCounter = parseInt(retakeCounterStr, 10);

					GamificationCounterStr = TempSuspendData['Gamification'];
					var GamificationCounterStrSplit1 = GamificationCounterStr.split(",");

					GamificationComputerScore = 0;
					GamificationUserScore = 0;

					if (GamificationCounterStrSplit1.length >= 2) {
						GamificationComputerScore = parseInt(GamificationCounterStrSplit1[0]);
						GamificationUserScore = parseInt(GamificationCounterStrSplit1[1]);

						for (var i = 2; i < GamificationCounterStrSplit1.length; i++) {
							if (GamificationCounterStrSplit1[i] != "") {
								GamificationScoreArray.push(parseInt(GamificationCounterStrSplit1[i]));
							}
						}
					}

          PreExamSkipModules = TempSuspendData['SkipModule'];
          if (typeof PreExamSkipModules === 'undefined') {
            PreExamSkipModules = "";
          }

          PreExamScorePercentage = TempSuspendData['PreExamScorePercentage'];
          PreExamInteractionId =  TempSuspendData['PreExamInteractionID'];

          QuizSuspendData = TempSuspendData['QuizSuspendData'];

          UserHistory = TempSuspendData['History'];
				}
			}

			WriteToDebug_2004("..Suspend Data = " + SuspendData.toString());
			//GetPreExamValueFromSuspendData_2004(SuspendData);
			if (RECORD_INTERACTIONS) {
				WriteToDebug_2004("..RECORD_INTERACTIONS = " + RECORD_INTERACTIONS.toString());
				if (OVERWRITE_QUESTIONS) {
					InteractionID = 0;
				}
				else {
					InteractionID = SCORM2004_CallGetValue("cmi.interactions._count");
				}

				if (admin_HostedOniLMS == true && PreExamEnabled == true)
				{
					InteractionID = PreExamInteractionId;
				}
				else
				{
					InteractionID = SCORM2004_CallGetValue("cmi.interactions._count");
					if(InteractionID == "") InteractionID = 0;
				}
				WriteToDebug_2004("..HostedOniLMS = " + admin_HostedOniLMS + " , PreExamFile = " + admin_PreExamFile);
				WriteToDebug_2004("..Interaction Count = " + InteractionID);
			}
			//console.log("BookMark: "+ LastBookmark + ", Suspend Data: "+ SuspendData );
			return true;
		}
		else
		{
			return false;
		}
	}
	else
	{
		return false;
	}
}

function UpdateBookmark_2004(ModuleID, PageID, PageIDInt)
{
	WriteToDebug_2004("Calling UpdateBookmark_2004 Function");
	if (ScormInitialized && !admin_ReviewMode)
	{
		if (PageIDInt > LatestBookmarkPageID) {
			LatestBookmarkPageID = PageIDInt;
			//console.log(ModuleID,PageID);
			WriteToDebug_2004("..Setting Bookmark = " + ModuleID + "-" + PageID);
			SCORM2004_SetBookmark(ModuleID + "-" + PageID);

			WriteToDebug_2004("......Calling VerifyData_2004 for Bookmark verification");
			var verificationResult = VerifyData_2004("bookmark", ModuleID + "-" + PageID);
			WriteToDebug_2004("......Result of Bookmark Verification = " + verificationResult);
			if (!verificationResult)
				alert(ERROR_CODE + " -- " + lang040);
		}

		//update suspend data with bookmark in case final exam doesnt report each question to scorm
		var TempSuspendData = {'Retake':admin_FinalRetakeCounter, 'Gamification':GamificationSuspendData, 'PreExamInteractionID':PreExamInteractionId, 'PreExamScorePercentage':PreExamScorePercentage, 'SkipModule':PreExamSkipModules, 'QuizSuspendData':QuizSuspendData, 'History':UserHistory};

		var TempSuspendString = JSON.stringify(TempSuspendData);

//		console.log('write suspend data:');
//		console.log(TempSuspendString + "|" + SuspendData);

    // save suspend data : Left side of "|" belongs to iEngine and right side to iLMS

    WriteToDebug_2004("..Setting Suspend Data as = " + TempSuspendString + "|" + SuspendData.toString());
		SCORM2004_SetSuspendData(TempSuspendString + "|" + SuspendData);

		SCORM2004_CallCommit();
	}
}

function AddScormQuizAnswer_2004(QuestionID, QuestionText, AnswerTexts, CorrectAnswerText, UserAnswerText, AnswerIsCorrect)
{
	//console.log( QuestionID + " , " + AnswerTexts + " , " + CorrectAnswerText + " , " + UserAnswerText + " , " + AnswerIsCorrect );
	//console.log(SuspendData);
	WriteToDebug_2004("Calling AddScormQuizAnswer_2004 Function");
	WriteToDebug_2004("..QuestionId = " + QuestionID);
	WriteToDebug_2004("..QuestionText = " + striphtmlcode(QuestionText));
	WriteToDebug_2004("..AnswerTexts = " + striphtmlcode(AnswerTexts));
	WriteToDebug_2004("..CorrectAnswerText = " + CorrectAnswerText.toString());
	WriteToDebug_2004("..UserAnswerText = " + UserAnswerText);
	WriteToDebug_2004("..AnswerIsCorrect = " + AnswerIsCorrect);
	//this function will be called at the end of the lesson for all quiz questions answered (will only be called together with SetLessonPassed when learner is successful)


	if (ScormInitialized && !admin_ReviewMode)
	{
		/*
		 **
		 *currently this gives error:
		 *[08:32:16.675] LMSSetValue('cmi.interactions.Question_4.id', 'Question 4') returned 'false' in 0.001 seconds
		 *[08:32:16.676] CheckForSetValueError (cmi.interactions.Question_4.id, Question 4, cmi.interactions.Question_n.id, , )
		 *[08:32:16.676] SCORM ERROR FOUND - Set Error State: 201 - The parameter 'cmi.interactions.Question_4.id' is not recognized.
		 *
		 *
		 var QuestionID2 = QuestionID.replace(" ","_");
		 LMSSetValue( "cmi.interactions."+QuestionID2+".id", QuestionID );
		 LMSSetValue( "cmi.interactions."+QuestionID2+".type", "choice" );
		 LMSSetValue( "cmi.interactions."+QuestionID2+".student_response", UserAnswerText );
		 LMSSetValue( "cmi.interactions."+QuestionID2+".correct_responses.1.pattern", CorrectAnswerText );
		 LMSSetValue( "cmi.interactions."+QuestionID2+".result", AnswerIsCorrect );
		 */
		//WriteToDebug_2004("..RECORD_INTERACTIONS = " + RECORD_INTERACTIONS.toString());

		//QuestionID = "urn:IEL:" + QuestionID;
		QuestionText = "urn:IEL:" + striphtmlcode(QuestionText);
		//UserAnswerText = "urn:IEL:" + UserAnswerText;
		//CorrectAnswerText = "urn:IEL:" + CorrectAnswerText;

		if (RECORD_INTERACTIONS) {
			if (admin_HostedOniLMS) {
				WriteToDebug_2004("..Recording Interaction for ID = " + InteractionID.toString());
				SCORM2004_CallSetValue("cmi.interactions." + InteractionID + ".id", QuestionID.toString());
				SCORM2004_CallSetValue("cmi.interactions." + InteractionID + ".type", "choice");
				SCORM2004_CallSetValue("cmi.interactions." + InteractionID + ".learner_response", UserAnswerText.toString());
				SCORM2004_CallSetValue("cmi.interactions." + InteractionID + ".correct_responses.0.pattern", CorrectAnswerText.toString());
				if (AnswerIsCorrect.toString().toLowerCase() == "true")
					AnswerIsCorrect = "correct";
				if (AnswerIsCorrect.toString().toLowerCase() == "false")
					AnswerIsCorrect = "incorrect";
				SCORM2004_CallSetValue("cmi.interactions." + InteractionID + ".result", AnswerIsCorrect);
				InteractionID = parseInt(InteractionID) + 1;
			}
			else {
				WriteToDebug_2004("..Recording Interaction for ID = " + InteractionID.toString());
				SCORM2004_CallSetValue("cmi.interactions." + InteractionID + ".id", baseInteractionIdentifier + (parseInt(InteractionID) + 1).toString());
				SCORM2004_CallSetValue("cmi.interactions." + InteractionID + ".type", "choice");
				SCORM2004_CallSetValue("cmi.interactions." + InteractionID + ".learner_response", UserAnswerText.toString());
				SCORM2004_CallSetValue("cmi.interactions." + InteractionID + ".correct_responses.0.pattern", CorrectAnswerText.toString());
				if (AnswerIsCorrect.toString().toLowerCase() == "true")
					AnswerIsCorrect = "correct";
				if (AnswerIsCorrect.toString().toLowerCase() == "false")
					AnswerIsCorrect = "incorrect";
				SCORM2004_CallSetValue("cmi.interactions." + InteractionID + ".result", AnswerIsCorrect);
				InteractionID = parseInt(InteractionID) + 1;
			}
		}
	}
}

function CloseCourse_2004(CourseFailed)
{
	WriteToDebug_2004("Calling CloseCourse_2004 Function");
	if (ScormInitialized)
	{

		if (!admin_ReviewMode)
		{
			if (CourseFailed)
			{
				if ((admin_FinalRetakeTillPass) && (admin_FinalRetakeCounter < admin_FinalRetakeMaxCount))
				{
					SetCourseRetake_2004();
				}
			} else
			{
				WriteToDebug_2004("..LessonComplete = " + LessonComplete.toString());
				if (!LessonComplete) {
					SCORM2004_SetInComplete();
				}
				else {
					SCORM2004_SetBookmark("0");
					if (DISPLAY_CERTIFICATE)
					{
						window.open("xmls/en/certificate.htm?studentname=" + StudentName, "_new", "toolbar=no, menubar=no, status=no, location=no,height=500, width=700");
					}
				}
			}
		}
		else
		{
			if (DISPLAY_CERTIFICATE_FOR_COMPLETED_COURSE)
			{
				window.open("xmls/en/certificate.htm?studentname=" + StudentName, "_new", "toolbar=no, menubar=no, status=no, location=no,height=500, width=700");
			}
		}

		WriteToDebug_2004("..Setting Session Time as = " + getElapsedTime());
		SCORM2004_CallSetValue("cmi.session_time", getElapsedTime());
		SCORM2004_CallSetValue("cmi.exit", "suspend");
		WriteToDebug_2004("..Calling SCORM2004_CallTerminate");
		SCORM2004_CallCommit();
		top.close();
	} else
	{
		//navigate to urlonExit
		if (admin_URLOnExit != "") {
			try
			{
				window.location.href = admin_URLOnExit;
			}
			catch (e)
			{
				// do nothing
			}
			//window.location.assign("http://www.google.com");
		}
	}
}

function unloadPage_2004()
{
	WriteToDebug_2004("Calling unloadPage_2004 Function");
	CloseCourse_2004(false);
	WriteToDebug_2004("..Is Already Terminated = " + terminated.toString());
	if (!terminated)
		SCORM2004_CallTerminate();
}

function SetLessonPassed_2004(ScorePercentage, HasPassedQuiz)
{
	//console.log(ScorePercentage+" "+HasPassedQuiz+" "+ScormInitialized);
	//this function will be called at the end of the lesson after the learner is successful with the quiz)
	WriteToDebug_2004("Calling SetLessonPassed_2004 Function");
	WriteToDebug_2004("..ScorePercentage = " + ScorePercentage.toString());
	WriteToDebug_2004("..HasPassedQuiz = " + HasPassedQuiz.toString());
	if (ScormInitialized && !admin_ReviewMode)
	{
		WriteToDebug_2004("..Setting Score");
		SCORM2004_SetScore(ScorePercentage.toString(), "100", "0");

		WriteToDebug_2004("......Calling VerifyData_2004 for Score verification");
		var verificationResult = VerifyData_2004("score", ScorePercentage.toString());
		WriteToDebug_2004("......Result of Score Verification = " + verificationResult);
		if (!verificationResult)
			alert(ERROR_CODE + " -- " + lang041);

		SCORM2004_SetBookmark("0");
		LessonComplete = true;
		if (HasPassedQuiz)
		{
			WriteToDebug_2004("..Setting Success Status as Passed");
			SCORM2004_SetPassed(); // cmi.success_status, cmi.completion_status
			WriteToDebug_2004("......Calling VerifyData_2004 for Success Status verification");
			var verificationResult = VerifyData_2004("success_status", "passed");
			WriteToDebug_2004("......Result of Success Status Verification = " + verificationResult);
			if (!verificationResult)
				alert(ERROR_CODE + " -- " + lang042);
		}
		else
		{
			WriteToDebug_2004("..Setting Success Status as failed");
			SCORM2004_SetFailed(); // cmi.success_status, cmi.completion_status
			WriteToDebug_2004("......Calling VerifyData_2004 for Success Status verification");
			var verificationResult = VerifyData_2004("success_status", "failed");
			WriteToDebug_2004("......Result of Success Status Verification = " + verificationResult);
			if (!verificationResult)
				alert(ERROR_CODE + " -- " + lang042);
		}
	}
}

function SetScormCoursePassed_2004()
{
	//console.log(ScorePercentage+" "+HasPassedQuiz+" "+ScormInitialized);
	//this function will be called at the end of the lesson after the learner is successful with the quiz)
	WriteToDebug_2004("Calling SetScormCoursePassed_2004 Function");
	if (ScormInitialized && !admin_ReviewMode)
	{
		LessonComplete = true;

		SCORM2004_SetBookmark("0");

		WriteToDebug_2004("..Setting Completion Status as completed");
		SCORM2004_SetCompleted();

		WriteToDebug_2004("......Calling VerifyData_2004 for Completion Status verification");
		verificationResult = VerifyData_2004("completion_status", "completed");
		WriteToDebug_2004("......Result of Completion Status Verification = " + verificationResult);
		if (!verificationResult)
			alert(ERROR_CODE + " -- " + lang042);
	}
}

function VerifyData_2004(dataElement, valueFromCourse) {
	WriteToDebug_2004("........In VerifyData_2004 for = " + dataElement);
	var result = true;
	var _155;
	if (dataElement.toLowerCase() == "bookmark") {
		_155 = SCORM2004_GetBookmark();
		_155 = _155 + '';
		if (_155 != valueFromCourse) {
			WriteToDebug_2004("........value is not matching from LMS, retrying...");
			for (var i = 0; i < RETRY_ATTEMPT - 1; i++) {
				SCORM2004_SetBookmark(valueFromCourse);
				var ERROR_CODE = SCORM2004_GetLastError().toString();
				if (ERROR_CODE.toString() == "0" || ERROR_CODE.toString() == "") {
					result = true;
					break;
				}
				else {
					result = false;
				}
			}
		}
	}
	if (dataElement.toLowerCase() == "completion_status") {
		_155 = SCORM2004_GetCompletionStatus();
		_155 = _155 + '';
		if (_155 != valueFromCourse) {
			WriteToDebug_2004("........value is not matching from LMS, retrying...");
			for (var i = 0; i < RETRY_ATTEMPT - 1; i++) {
				SCORM2004_CallSetValue("cmi.completion_status", valueFromCourse);
				var ERROR_CODE = SCORM2004_GetLastError().toString();
				if (ERROR_CODE.toString() == "0" || ERROR_CODE.toString() == "") {
					result = true;
					break;
				}
				else {
					result = false;
				}
			}
		}
	}
	if (dataElement.toLowerCase() == "success_status") {
		_155 = SCORM2004_GetSuccessStatus();
		_155 = _155 + '';
		if (_155 != valueFromCourse) {
			WriteToDebug_2004("........value is not matching from LMS, retrying...");
			for (var i = 0; i < RETRY_ATTEMPT - 1; i++) {
				SCORM2004_CallSetValue("cmi.success_status", valueFromCourse);
				var ERROR_CODE = SCORM2004_GetLastError().toString();
				if (ERROR_CODE.toString() == "0" || ERROR_CODE.toString() == "") {
					result = true;
					break;
				}
				else {
					result = false;
				}
			}
		}
	}
	if (dataElement.toLowerCase() == "score") {
		_155 = SCORM2004_GetScore(); // cmi.score.raw
		_155 = _155 + '';
		if (_155 != valueFromCourse) {
			WriteToDebug_2004("........value is not matching from LMS, retrying...");
			for (var i = 0; i < RETRY_ATTEMPT - 1; i++) {
				SCORM2004_SetScore(valueFromCourse, "100", "0");
				var ERROR_CODE = SCORM2004_GetLastError().toString();
				if (ERROR_CODE.toString() == "0" || ERROR_CODE.toString() == "") {
					result = true;
					break;
				}
				else {
					result = false;
				}
			}
		}
	}
	return result;
}

function SetCourseRetake_2004() {
	CourseRetake = true;
	FirstExamPage = true;
	if (ScormInitialized && !admin_ReviewMode) {
		WriteToDebug_2004("Calling SetCourseRetake_2004 Function");
		WriteToDebug_2004("..Setting Bookmark as blank");

		LatestBookmarkPageID = 0;
		SCORM2004_SetBookmark("0≈");
		WriteToDebug_2004("......Calling VerifyData_2004 for Bookmark verification");
		var verificationResult = VerifyData_2004("bookmark", "");
		WriteToDebug_2004("......Result of Bookmark Verification = " + verificationResult);
		if (!verificationResult)
			alert(ERROR_CODE + " -- " + lang042);

		WriteToDebug_2004("..Setting Completion Status as incopmlete");
		SCORM2004_SetInComplete();

		WriteToDebug_2004("..Setting Score as zero");
//	SCORM2004_CallSetValue("cmi.core.score.raw","0"); ------------------------------- **** SOME LMS missunderstand this as the course is completed with fail
		WriteToDebug_2004("......Calling VerifyData_2004 for Score verification");
		var verificationResult = VerifyData_2004("score", "0");
		WriteToDebug_2004("......Result of Score Verification = " + verificationResult);
		if (!verificationResult)
			alert(ERROR_CODE + " -- " + lang042);

		WriteToDebug_2004("..Setting SuspendData as blank");
		SCORM2004_SetSuspendData("|");
	}

}

function striphtmlcode(html)
{
	var tmp = document.createElement("DIV");
	tmp.innerHTML = html;
	return tmp.textContent || tmp.innerText || "";
}

function ScormPreExamSkipNotification_2004()
{
}

function AddScormPreExamAnswer_2004(QuestionID, QuestionText, AnswerTexts, CorrectAnswerText, UserAnswerText, AnswerIsCorrect, QuestionModules)
{
	//console.log("QuestionID: "+ striphtmlcode(QuestionID) );
	//console.log("QuestionText: "+ striphtmlcode(QuestionText) );
	//console.log("Answers: "+ striphtmlcode(AnswerTexts) );
	//console.log("Correct Answer: "+ CorrectAnswerText );
	//console.log("User Choice: "+ UserAnswerText );
	//console.log("is Correct: "+ AnswerIsCorrect );
	WriteToDebug_2004("Calling AddScormPreExamAnswer_2004 Function");
	WriteToDebug_2004("..QuestionId = " + QuestionID);
	WriteToDebug_2004("..QuestionText = " + striphtmlcode(QuestionText));
	//WriteToDebug_2004("..AnswerTexts = " + AnswerTexts);
	WriteToDebug_2004("..CorrectAnswerText = " + CorrectAnswerText.toString());
	WriteToDebug_2004("..UserAnswerText = " + UserAnswerText);
	WriteToDebug_2004("..AnswerIsCorrect = " + AnswerIsCorrect);

	if (ScormInitialized && !admin_ReviewMode)
	{
		if (RECORD_INTERACTIONS && admin_HostedOniLMS) {
			WriteToDebug_2004("..Recording Interaction for ID = " + InteractionID.toString());
			SCORM2004_CallSetValue("cmi.interactions." + InteractionID + ".id", QuestionID.toString());
			SCORM2004_CallSetValue("cmi.interactions." + InteractionID + ".type", "choice");
			SCORM2004_CallSetValue("cmi.interactions." + InteractionID + ".learner_response", UserAnswerText.toString());
			SCORM2004_CallSetValue("cmi.interactions." + InteractionID + ".correct_responses.0.pattern", CorrectAnswerText.toString());
			if (AnswerIsCorrect.toString().toLowerCase() == "true") {
				AnswerIsCorrect = "correct";
				WriteToDebug_2004("..PreExamAdaptiveTraining = " + PreExamAdaptiveTraining);
				if (PreExamAdaptiveTraining) {
					WriteToDebug_2004("..Adding QuestionModules");
				}
			}
			if (AnswerIsCorrect.toString().toLowerCase() == "false")
				AnswerIsCorrect = "incorrect";
			SCORM2004_CallSetValue("cmi.interactions." + InteractionID + ".result", AnswerIsCorrect);
			InteractionID = parseInt(InteractionID) + 1;
		}
	}
}

function AddScormPreExamResult_2004(Percentage)
{
  if (admin_HostedOniLMS) {
    PreExamInteractionId = InteractionID;
    WriteToDebug_2004("..Calling AddScormPreExamResult Function");
    //iEngine will call UpdateBookmark right after this so the PreExamInteractionId will be saved
  }
}

function ResetInteractionIDOnExamRetake() {
	WriteToDebug_2004("..Calling ResetInteractionIDOnExamRetake function");
	InteractionID = PreExamInteractionId;
}

function AddScormSurveyAnswer_2004(QuestionID, QuestionText, AnswerTexts, UserAnswerText, UserAnswerMemo)
{
	// QuestionID contains question ID
	// QuestionText contains question text
	// AnswerTexts contains all options (including text)
	// UserAnswerText contains selected choice by the user. In case of free form question, this contains blank
	// UserAnswerMemo contains free form answer entered by the user. In case question doesn't have this option, then it will return as undefined
	//alert("Survey Question: "+ striphtmlcode(QuestionID) );
	//alert("Answers: "+ striphtmlcode(AnswerTexts) );
	//alert("User Choice: "+ UserAnswerText );
	//alert("User Memo: "+ UserAnswerMemo );

	WriteToDebug_2004("Calling AddScormSurveyAnswer Function");
	WriteToDebug_2004("..QuestionId = " + QuestionID);
	WriteToDebug_2004("..QuestionText = " + striphtmlcode(QuestionText));
	WriteToDebug_2004("..AnswerTexts = " + striphtmlcode(AnswerTexts));
	WriteToDebug_2004("..UserAnswerText = " + UserAnswerText);
	WriteToDebug_2004("..UserAnswerMemo = " + UserAnswerMemo);

	if (ScormInitialized && !admin_ReviewMode)
	{
		if (RECORD_INTERACTIONS && admin_HostedOniLMS) {
			var surveyQuestionCode = ""; // F - Free Form, M - Multiple Choice, S - Multiple Choice + Free Form
			if (UserAnswerMemo != null && UserAnswerMemo != 'undefined') {
				if (UserAnswerText == "") {
					surveyQuestionCode = "F";
				}
				else {
					surveyQuestionCode = "S";
				}
			}
			else {
				surveyQuestionCode = "M";
			}

			switch (surveyQuestionCode) {
				case "F":
					WriteToDebug_2004("..Recording Survey Interaction for ID = " + InteractionID.toString());
					SCORM2004_CallSetValue("cmi.interactions." + InteractionID + ".id", QuestionID.toString());
					SCORM2004_CallSetValue("cmi.interactions." + InteractionID + ".type", "fill-in");
					SCORM2004_CallSetValue("cmi.interactions." + InteractionID + ".learner_response", UserAnswerMemo.toString());
					//SCORM2004_CallSetValue( "cmi.interactions."+InteractionID+".correct_responses.0.pattern", CorrectAnswerText.toString());
					SCORM2004_CallSetValue("cmi.interactions." + InteractionID + ".result", "correct");
					InteractionID = parseInt(InteractionID) + 1;
					break;
				case "M":
					WriteToDebug_2004("..Recording Survey Interaction for ID = " + InteractionID.toString());
					SCORM2004_CallSetValue("cmi.interactions." + InteractionID + ".id", QuestionID.toString());
					SCORM2004_CallSetValue("cmi.interactions." + InteractionID + ".type", "choice");
					SCORM2004_CallSetValue("cmi.interactions." + InteractionID + ".learner_response", UserAnswerText.toString());
					//SCORM2004_CallSetValue( "cmi.interactions."+InteractionID+".correct_responses.0.pattern", CorrectAnswerText.toString());
					SCORM2004_CallSetValue("cmi.interactions." + InteractionID + ".result", "correct");
					InteractionID = parseInt(InteractionID) + 1;
					break;
				case "S":
					WriteToDebug_2004("..Recording Survey Interaction for ID = " + InteractionID.toString());
					SCORM2004_CallSetValue("cmi.interactions." + InteractionID + ".id", QuestionID.toString() + ".1");
					SCORM2004_CallSetValue("cmi.interactions." + InteractionID + ".type", "choice");
					SCORM2004_CallSetValue("cmi.interactions." + InteractionID + ".learner_response", UserAnswerText.toString());
					//SCORM2004_CallSetValue( "cmi.interactions."+InteractionID+".correct_responses.0.pattern", CorrectAnswerText.toString());
					SCORM2004_CallSetValue("cmi.interactions." + InteractionID + ".result", "correct");
					InteractionID = parseInt(InteractionID) + 1;

					SCORM2004_CallSetValue("cmi.interactions." + InteractionID + ".id", QuestionID.toString() + ".2");
					SCORM2004_CallSetValue("cmi.interactions." + InteractionID + ".type", "fill-in");
					SCORM2004_CallSetValue("cmi.interactions." + InteractionID + ".learner_response", UserAnswerMemo.toString());
					//SCORM2004_CallSetValue( "cmi.interactions."+InteractionID+".correct_responses.0.pattern", CorrectAnswerText.toString());
					SCORM2004_CallSetValue("cmi.interactions." + InteractionID + ".result", "correct");

					InteractionID = parseInt(InteractionID) + 1;
					break;
			}

		}
	}
}

function getElapsedTime() {
	endtime = new Date();
	var tottime = Math.round((endtime.getTime() - startTime.getTime()) / 1000.);
	var hr, min, sec;
	hr = Math.floor(tottime / 3600);
	min = Math.floor((tottime - (hr * 3600)) / 60);
	sec = tottime - hr * 3600 - min * 60;
	//var eltime=format2(hr)+":"+format2(min)+":"+format2(sec);
	var eltime = "PT" + hr + "H" + min + "M";
	delete endtime;
	return eltime;
}


function Scorm2004_Post_Quiz_Answer(QuizQuestionID,AnswerID,IsCorrect)
{
	//alert("Scorm2004 ID: "+QuizQuestionID+", Answer: "+AnswerID+", Correct: "+IsCorrect);
	if(IsStringNullOrEmpty(QuizQuestionID) != "")
	{
		WriteToDebug("Calling Scorm_Post_Quiz_Answer Function");
		WriteToDebug("..QuizQuestionID = " + QuizQuestionID);
		WriteToDebug("..AnswerID = " + AnswerID);
		WriteToDebug("..IsCorrect = " + IsCorrect.toString());

		if (ScormInitialized && !admin_ReviewMode)
		{
			if (RECORD_INTERACTIONS && admin_HostedOniLMS) {
				WriteToDebug("..Recording Interaction for ID = " + InteractionID.toString());
				LMSSetValue("cmi.interactions." + InteractionID + ".id", QuizQuestionID.toString());
				LMSSetValue("cmi.interactions." + InteractionID + ".type", "choice");
				LMSSetValue("cmi.interactions." + InteractionID + ".learner_response", AnswerID.toString());
				//LMSSetValue("cmi.interactions." + InteractionID + ".correct_responses.0.pattern", CorrectAnswerText.toString());
				if (IsCorrect.toString().toLowerCase() == "true")
					IsCorrect = "correct";
				if (IsCorrect.toString().toLowerCase() == "false")
					IsCorrect = "incorrect";
				LMSSetValue("cmi.interactions." + InteractionID + ".result", IsCorrect);
				InteractionID = parseInt(InteractionID) + 1;
			}
		}
	}

}
