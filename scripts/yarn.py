#!/usr/bin/env python
import json
import requests
import time
import sys
from ConfigParser import SafeConfigParser
from requests_kerberos import HTTPKerberosAuth
from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

def parameters():
        if mode == "completed":
            endtime = int(round((time.time() - 60) * 1000))
            params = {'states' : 'FINISHED', 'finishedTimeBegin' : endtime }
            return(params)
        else:
            params = {'states': 'RUNNING'}
            return(params)
def AmbariRest():
    url = ambariServer + "/api/v1/clusters/" + clusterName  + "alerts?fields=*"
    r = requests.get(url, verify=False, auth=(username, password))
    return(json.loads(r.text))

def YARNRest() :
    url = resourceManager + "/ws/v1/cluster/apps"
    r = requests.get(url, allow_redirects=True, verify=False, params = parameters())
    return(json.loads(r.text))

def TimelineRest(entityid, params):
    url = timeLineServer + "/ws/v1/timeline/" + entityid
    if krb5Auth:
        auth = HTTPKerberosAuth()
    else:
        auth = None
    r = requests.get(url, auth=auth, verify=False, params=params)
    response = json.loads(r.text)
    return(response['entities'])

def timelinefilter(sessionid):
    params = {'secondaryFilter' : 'SESSION_ID:%s' % (sessionid)}
    username = TimelineRest('HIVE_QUERY_ID', params)[0]['primaryfilters']['requestuser']
    return(username.split('@')[0])

def YARNJobs():
    List =[]
    outputlist = ['id', 'user', 'queue', 'state', 'finalStatus', 'progress', 'applicationType', 'startedTime', 'finishedTime', 'elapsedTime', 'allocatedMB', 'allocatedVCores', 'runningContainers', 'memorySeconds', 'vcoreSeconds', 'queueUsagePercentage', 'clusterUsagePercentage', 'preemptedResourceMB', 'preemptedResourceVCores', 'name']
    for app in YARNRest()['apps']['app']:
        filtered = dict((k, app[k]) for k in outputlist if k in app)
        elpasedtime = filtered['elapsedTime'] / 1000
        filtered.update({'elapsedTime' : elpasedtime})
        filtered.update({'type' : 'yarnJobs'})
        List.append(filtered)
    return(List)

def ambarialerts():
    List =[]
    startedTime = int(round( time.time() - 60))
    for alert in AmbariRest()['items']:
        filtered = dict((k, v) for k, v in alert.items() if v['state'] == 'CRITICAL' and v['original_timestamp'] >= startedTime)
        filtered.update('type':'serviceMonitor')
        List.append(filtered)
    return(List)

def YARNaggregate():
    totalclusterusage = 0
    totalcpucores = 0
    totalmemorymb = 0
    totalcontainers = 0
    for job in YARNJobs():
        totalclusterusage += job['clusterUsagePercentage']
        totalcpucores += job['allocatedVCores']
        totalmemorymb += job['allocatedMB']
        totalcontainers += job['runningContainers']
    List = {'totalclusterusage' : totalclusterusage, 'totalcpucores' : totalcpucores, 'totalmemorymb': totalmemorymb, 'totalcontainers': totalcontainers, 'type' : 'YARNaggregate' }
    return(List)

def yarnJob(yarnJobs):
    for job in yarnJobs:
        if hhiveImpersonationFilter == True:# and job['user'] == 'hive':
            sessionid = job['name'].split('-',1)[1]
            job.update('user', timelinefilter(sessionid))
            #print timelinefilter(sessionid)
        print job

def alerts(alerts):
    for alert in  alerts:
        print alert

def configs():
    try:
        configfile=sys.argv[1]
    except IndexError:
        print("Provide config file location", file=sys.stderr)
        sys.exit(1)
    settings = SafeConfigParser()
    settings.read(configfile)
    properties = ['YARN.resourceManager','Ambari.ambariServer', 'Ambari.username', 'Ambari.password', 'Ambari.clusterName', 'YARN.krb5Auth', 'YARN.hiveImpersonationFilter', 'YARN.timeLineServer']
    for prop in properties:
        variable = prop.split('.')[1]
        section = prop.split('.')[0]
        try:
            globals()[variable] = settings.get(section, variable)
        except:
            print("property " + variable + " is missing", file=sys.stderr )
            sys.exit(1)


def run():
    configs()
    global mode
    mode = 'completed'
    try:
        yarnJob(YARNJobs())
    except:
        print("Error while gathering YARN Completed Jobs", file=sys.stderr)
        pass
    mode = 'running'
    try:
        yarnJob(YARNJobs())
    except:
        print("Error while gathering YARN Running Jobs", file=sys.stderr)
        pass
    try:
        print YARNaggregate()
    except:
        print("Error while gathering YARN Aggregate", file=sys.stderr)
        pass
    try:
        alerts(ambarialerts)
    except:
        print("Error while gathering ambari alerts", file=sys.stderr)
        pass

try:
    run()
except:
    print("errors while running the program", file=sys.stderr)
    sys.exit(1)