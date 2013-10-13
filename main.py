from lectioapi import asignments
import requests
from datetime import *
from pytz import timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from googleauth import google_oauth
from googlecalendar import calendar as GoogleCalendarObject
import config as appConfig

# Converts a dict data structure into a class
class dic2class(dict):
    def __init__(self, dic):
        for key,val in dic.items():
            self.__dict__[key]=self[key]=dic2class(val) if isinstance(val,dict) else val

def createTitle(event):
    return event["title"]

def sameEvent(googleEvent,localEvent):
    return localEvent["link"] == googleEvent["description"]

__author__ = "Bo Thomsen <bo@illution.dk>"

# Crete the database Engine
engine = create_engine(appConfig.database+'://'+appConfig.db_user+':'+appConfig.db_password+'@'+appConfig.db_host+'/'+appConfig.db_database_name)

Session = sessionmaker(bind=engine)

# create a Session
session = Session()

tasks = session.execute("SELECT * FROM assignment_tasks")

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

    assignmentList = asignments.assignments(dic2class(settings))

    if len(assignmentList) > 0:
        tokenQuery = session.execute('SELECT * FROM user WHERE user_id="'+task["google_id"]+'"')

        GoogleOAuth = google_oauth.GoogleOAuth()

        for row in tokenQuery:
            refreshToken = row["refresh_token"]
            accessTokenData = GoogleOAuth.refresh(refreshToken)
            accessToken = accessTokenData.access_token

        GoogleCalendar = GoogleCalendarObject.GoogleCalendar()
        GoogleCalendar.access_token = accessToken

        googleEvents = GoogleCalendar.events(task["calendar_id"], {
            "timeZone" : "Europe/Copenhagen"
        })

        if not "items" in googleEvents:
            continue

        # Sync local -> Google
        for localEvent in assignmentList:
            localEvent["endDate"] = localEvent["date"] + timedelta(minutes = 10)
            found = False

            for googleEvent in googleEvents["items"]:
                if sameEvent(googleEvent,localEvent):
                    found = True

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
            for localEvent in assignmentList:
                if sameEvent(googleEvent, localEvent):
                    found = True

            if found == False:
                print "Delete"
                GoogleCalendar.deleteEvent(task["calendar_id"], googleEvent["id"])

    else:
        print "Error"