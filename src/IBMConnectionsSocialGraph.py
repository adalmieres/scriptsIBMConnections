
# coding: utf-8

# # IBM Connections Social Graph
# Un programme pour visualiser le graph social d'une installation IBM Connections
# Indiquez les informations de base dans la suite

# In[1]:

# url de votre serveur
serverUrl = ""
# votre id utilisateur
loginId = ""
# votre mot de passe
loginPwd = ""
# le userId de votre profil
loginUserId = ""

# dépendances
import requests
import xml.dom.minidom
import feedparser

# data structure
relations = []
knownUserIds = set()
unknownUserIds = set()
usersDetails = set()

# get userId relations
def getUserRelations(userId):
    # local variables
    userIds = []
    # get raw xml
    param = { 'userid' : userId, 'connectionType' : 'colleague', 'ps' : '250'}
    while True:
        try:
            r = requests.get('http://' + serverUrl + '/profiles/atom/connections.do', params=param, auth=(loginId,loginPwd))
        except:
            continue
        break
    # parse xml
    try:
        dom = xml.dom.minidom.parseString(r.text)
    except:
        return True
    feed = dom.firstChild
    entries = feed.getElementsByTagName('entry')
    for entry in entries:
        # get author user id
        author = entry.getElementsByTagName('author')[0]
        try:
            authorName = author.getElementsByTagName('name')[0]
            authorName = authorName.firstChild.data
        except:
            authorName = ""
        try:
            authorEMail = author.getElementsByTagName('email')[0]
            authorEMail = authorEMail.firstChild.data
        except:
            authorEMail = ""
        authorUserId = author.getElementsByTagName('snx:userid')[0]
        # get contributor user id
        contributor = entry.getElementsByTagName('contributor')[0]
        try:
            contribName = contributor.getElementsByTagName('name')[0]
            contribName = contribName.firstChild.data
        except:
            contribName = ""
        try:
            contribEMail = contributor.getElementsByTagName('email')[0]
            contribEMail = contribEMail.firstChild.data
        except:
            contribEMail = ""
        contribUserId = contributor.getElementsByTagName('snx:userid')[0]
        # add them to data structure
        relations.append(authorUserId.firstChild.data + ',' + contribUserId.firstChild.data)
        unknownUserIds.add(authorUserId.firstChild.data)
        unknownUserIds.add(contribUserId.firstChild.data)
        # add user datail to usersDetails set
        usersDetails.add(authorUserId.firstChild.data + ',' + authorName + ',' + authorEMail)
        usersDetails.add(contribUserId.firstChild.data + ',' + contribName + ',' + contribEMail)
    
    # add it to the knownUserIds set
    knownUserIds.add(userId)
    # remove already known user from unknownUserIds
    tmp = set(knownUserIds)
    for index, item in enumerate(tmp):
        if item in unknownUserIds:
            unknownUserIds.remove(item)
    
# get all relations of a set of userIds
def getAllRelations(setUserIds):
    while len(setUserIds) > 0:
        print ("still " + str(len(setUserIds)) + " to go.")
        tmpUserToCheck = set(setUserIds)
        for index, item in enumerate(tmpUserToCheck):
            print (index, end="\r")
            try:
                getUserRelations(item)
            except:
                continue
            
# search for userIds
def searchUserIds(search):
    # local variables
    nbPage = 0
    ps = 250
    # first page
    # requète
    while True:
        try:
            r = requests.get('http://' + serverUrl + '/profiles/atom/search.do?search=' + search + '*&ps=' + str(ps), auth=(loginId, loginPwd))
        except:
            continue
        break
    dom = xml.dom.minidom.parseString(r.text)
    feed = dom.firstChild
    totalResult = feed.getElementsByTagName('opensearch:totalResults')[0]
    totalResult = int(totalResult.firstChild.data)
    print (str(totalResult))
    if totalResult > ps:
        nbPage = int(float(totalResult) / ps) + 1
    else:
        nbPage = 1
    
    fundUserIds = feed.getElementsByTagName('snx:userid')
    ls = []
    for index, item in enumerate(fundUserIds):
        ls.append(item.firstChild.data)
    unknownUserIds.union(set(ls))
        
    
    # rest of the pages
    if nbPage > 1:
        for p in range(2,nbPage,1):
            # requète
            while True:
                try:
                    r = requests.get('http://' + serverUrl + '/profiles/atom/search.do?search=' + search + '*&ps=' + str(ps) + '&page=' + str(p), auth=(loginId, loginPwd))
                except:
                    continue
                break
            print ('page ' + str(p) + '/' + str(nbPage), end="\r")
            # parse
            dom = xml.dom.minidom.parseString(r.text)
            feed = dom.firstChild
            fundUserIds = feed.getElementsByTagName('snx:userid')
            for index, item in enumerate(fundUserIds):
                unknownUserIds.add(item.firstChild.data)
    

# write data
def writeUserDetails(mySet):
    f = open("usersDetails.csv","w")
    f.write("Id,Label,eMail\n")
    for line in mySet:
        f.write(line + '\n')
    f.close()

def writeRelations(myList):
    f = open("usersRelations.csv","w")
    f.write("Source,Target\n")
    for line in myList:
        f.write(line + '\n')
    f.close()

# run code
# init
searchUserIds("a")
# get all relations
getAllRelations(unknownUserIds)
# write down data in csv (for use in gephi)
writeUserDetails(usersDetails)
writeRelations(relations)
