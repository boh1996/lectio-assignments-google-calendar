from lectioapi import assignments
import requests
from datetime import *
from time import mktime
from pytz import timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from googleauth import google_oauth
from googlecalendar import calendar as GoogleCalendarObject
import config as appConfig
import calendar

# Converts a dict data structure into a class
class dic2class(dict):
    def __init__(self, dic):
        for key,val in dic.items():
            self.__dict__[key]=self[key]=dic2class(val) if isinstance(val,dict) else val

# Creates the calendar event title
def createTitle(event):
    return event["title"]

# Compares the google calendar event with the event from lectio, using startdate and the lectio link
def sameEvent(googleEvent,localEvent):
    timezone("Europe/Copenhagen")
    startTuple = localEvent["date"].utctimetuple()
    googleStartTuple = datetime.strptime(googleEvent["start"]["dateTime"][:-6], "%Y-%m-%dT%H:%M:%S").utctimetuple()

    return localEvent["link"] == googleEvent["description"] and calendar.timegm(googleStartTuple) == calendar.timegm(startTuple)

# Crete the database Engine
engine = create_engine('%s://%s:%s@%s/%s' % (appConfig.database, appConfig.db_user, appConfig.db_password, appConfig.db_host, appConfig.db_database_name))

# Create a Session
Session = sessionmaker(bind=engine)
session = Session()

# Fetches the tasks to run, from the tasks database
tasks = session.execute("SELECT * FROM assignment_tasks")

# Loops over the tasks
for task in tasks:
    settings = {
        # App Settings
        "lectio_base_url" : appConfig.lectio_base_url,
        "database" : appConfig.database,
        "db_password" : appConfig.db_password,
        "db_host" : appConfig.db_host,
        "db_database_name" : appConfig.db_database_name,
        "db_user" : appConfig.db_user,

        # User settings
        "password" : task["password"].decode("base64"),
        "username" : task["username"],
        "lectio_id" : task["lectio_id"],
        "school_id" : task["school_id"],
        "branch_id" : task["branch_id"],
        "calendar_id" : task["calendar_id"]
    }

    # Retrieve the assignments from lectio, using the lectio-api library
    assignmentObject = assignments.assignments(dic2class(settings))

    # If assignments is found
    if assignmentObject["status"] == "ok":
        assignmentList = assignmentObject["list"]

        # Retrive the Google Auth information from the table
        tokenQuery = session.execute('SELECT * FROM user WHERE user_id="%s"' % (task["google_id"]))

        GoogleOAuth = google_oauth.GoogleOAuth()

        # Fetch the refresh token, from the database result
        for row in tokenQuery:
            refreshToken = row["refresh_token"]
            # Fetch the access token from Google using the python-google-oauth library
            accessTokenData = GoogleOAuth.refresh(refreshToken)
            accessToken = accessTokenData.access_token

        # Assign the access token to the Google Calendar library
        GoogleCalendar = GoogleCalendarObject.GoogleCalendar()
        GoogleCalendar.access_token = accessToken

        # Retrieve the existing events from Google Calendar
        googleEvents = GoogleCalendar.events(task["calendar_id"], {
            "timeZone" : "Europe/Copenhagen"
        })

        # If the item key doesn't exist, an error has occurred, proceed to the next task
        if not "items" in googleEvents:
            continue

        # Sync local -> Google
        for localEvent in assignmentList:
            localEvent["endDate"] = localEvent["date"] + timedelta(minutes = 10)
            found = False

            # Loop through the Google events to find the local event
            for googleEvent in googleEvents["items"]:
                if sameEvent(googleEvent,localEvent):
                    found = True

            # If it doesn't exist, create it
            if found == False:
                GoogleCalendar.insertEvent(task["calendar_id"],{
                    "start" : {"timeZone" : "Europe/Copenhagen","dateTime" : localEvent["date"].strftime('%Y-%m-%dT%H:%M:%S.000')},
                    "end" : {"timeZone" : "Europe/Copenhagen","dateTime" : localEvent["endDate"].strftime('%Y-%m-%dT%H:%M:%S.000')},
                    "description" : localEvent["link"],
                    "summary" : createTitle(localEvent),
                })
            else:
                pass

        # Sync Google -> Local
        for googleEvent in googleEvents["items"]:
            found = False

            # Loop through the local events to find the Google event
            for localEvent in assignmentList:
                if sameEvent(googleEvent, localEvent):
                    found = True

            # If it doesn't exist there, delete it from Google Calendar
            if found == False:
                GoogleCalendar.deleteEvent(task["calendar_id"], googleEvent["id"])

        # Add Last updated timestamp
        session.execute('UPDATE assignment_tasks SET last_updated="%s" WHERE google_id="%s"' % (str(mktime(datetime.now().timetuple()))[:-2],task["google_id"]))
        session.commit()
    else:
        # Add Error to DB
        session.execute('INSERT INTO errors COLUMNS(system, error_time, error_type, user_id)' % ("assignments", str(mktime(datetime.now().timetuple()))[:-2], assignmentObject["type"],task["google_id"]))
        session.commit()

print "Done"