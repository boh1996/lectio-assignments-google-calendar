from lectioapi import asignments
import requests
import datetime
import config

assignmentList = asignments.assignments(config)

if len(assignmentList) > 0:
    print "Success"
else:
    print "Error"