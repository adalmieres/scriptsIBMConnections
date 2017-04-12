#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# dépendances
import requests
import xml.dom.minidom
import sys
import signal
import os
import getopt
from queue import Queue
from threading import Thread
import time

class SetQueue(Queue):

    def _init(self, maxsize):
        Queue._init(self, maxsize) 
        self.all_items = set()

    def _put(self, item):
        if item not in self.all_items:
            Queue._put(self, item) 
            self.all_items.add(item)

def signal_handler(signal, frame):
	print('You pressed Ctrl+C!')
	sys.exit(0)

def usage():
	"""usage de la ligne de commande"""
	print ("usage : " + sys.argv[0] + "-h --help -s --server someurl.com -u --user login -p --password password")

def getAtomFeed(url, login, pwd):
	# var
	MAX_TRY = 10
	essai = 0

	# get atom document
	while essai < MAX_TRY:
		try:
			r = requests.get('http://' + url, auth=(login,pwd), timeout=10)
		except:
			essai += 1
			continue
		break
	else:
		raise ('Erreur lors de la requête')

	# parse atom document
	try:
		dom = xml.dom.minidom.parseString(r.text)
	except:
		raise ('Erreur lors du parsing du document Atom')

	return dom

def getManagerInfo(atomFeed):
	try:
		entries = atomFeed.getElementsByTagName('entry')[1]
	except:
		return None
	try:
		managerId = entries.getElementsByTagName('snx:userid')[0]
		return managerId.firstChild.data
	except:
		return None

def buildUrlSearchList(server, login, pwd, q):
	# var
	alphabet = ['a','b','c','d','e','f','g','h','i','j','k','l','m','n','o','p','q','r','s','t','u','v','w','x','y','z']
	#alphabet = ['a']
	for i in alphabet:
		url = server + '/profiles/atom/search.do?search=' + i + '*&ps=250'
		dom = getAtomFeed(url, login, pwd)
		totalResult = dom.getElementsByTagName('opensearch:totalResults')[0]
		totalResult = int(totalResult.firstChild.data)
		if totalResult > 250:
			nbPage = int(float(totalResult) / 250) + 1
			for n in range(1,nbPage,1):
				item = url + "&page=" + str(n) 
				q.put(item)
		else:
			nbPage = 1
			q.put(url)

def getUserIdsWorker(login, pwd, qin, qout):
	while True:
		url = qin.get()
		if url == None:
			break
		qin.task_done()
		try:
			dom = getAtomFeed(url, login, pwd)
		except:
			continue
		userIds = dom.getElementsByTagName('snx:userid')
		for index, item, in enumerate(userIds):
			qout.put(item.firstChild.data)


def getRelationsWorker(server, login, pwd, qin, qout, getManager, qmgmt):
	while True:
		userid = qin.get()
		if userid == None:
			break
		qin.task_done()
		url = server + '/profiles/atom/connections.do?userid=' + userid + '&connectionType=colleague&ps=250'
		try:
			dom = getAtomFeed(url, login, pwd)
		except:
			continue
		feed = dom.firstChild
		entries = feed.getElementsByTagName('entry')
		for entry in entries:
			# get date
			dateRelation = entry.getElementsByTagName('updated')[0]
			dateRelation = dateRelation.firstChild.data
			dateRelation = dateRelation[:10]
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
			authorUserId = authorUserId.firstChild.data

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
			contribUserId = contribUserId.firstChild.data

			# build dict
			authorInfo = { "userid" : authorUserId, "name" : authorName, "email" : authorEMail }
			contribInfo = { "userid" : contribUserId, "name" : contribName, "email" : contribEMail }
			relation = "\"" + authorUserId + "\",\"" + contribUserId + "\",\"<(" + str(dateRelation) + ",Infinity)>\""
			qout.put(authorInfo)
			qout.put(contribInfo)
			qout.put(relation)

		# get manager
		if getManager == True:
			url = server + "/profiles/atom/reportingChain.do?userid=" + userid
			rc = getAtomFeed(url, login, pwd)
			managerId = getManagerInfo(rc)
			if managerId is not None:
				reportingChain = str(userid) + "," + str(managerId)
				qmgmt.put(reportingChain)
			

def printStatusThread(q0, q1, q2, q3):
	strtime = time.time()
	while True:
		sys.stdout.write('\r\x1b[K')
		sys.stdout.write("urls:" + str(q0.qsize()) + " | ")
		sys.stdout.write("userids:" + str(q1.qsize()) + " | ")
		sys.stdout.write("user infos:" + str(q2.qsize()) + " | ")
		sys.stdout.write("manager infos:" + str(q3.qsize()))
		sys.stdout.flush()
		time.sleep(1)

def writeFileThread(usersFilename, relationsFilename, qin):
	# file for user details
	u = open(usersFilename + ".csv", "w")
	u.write("Id,Label,eMail\n")
	# file for relations
	r = open(relationsFilename + ".csv", "w")
	r.write("Source,Target,Time Interval\n")	
	
	doneUsers = []
	while True:
		data = qin.get()
		if data == None:
			u.flush()
			r.flush()
			u.close()
			r.close()
			break
		# write data
		if type(data) is dict:
			string = str(data["userid"]) + ',' + str(data["name"]) + ',' + str(data["email"])
			if string not in doneUsers:
				u.write(string + "\n")
				doneUsers.append(string)
		elif type(data) is str:
			r.write(str(data) + "\n")
		qin.task_done()

def writeManagerFileThread(managerFilename, qin):
	m = open(managerFilename + ".csv", "w")
	m.write("Source,Target\n")
	while True:
		data = qin.get()
		if data == None:
			break
		m.write(str(data) + "\n")
		qin.task_done()
		

def main(argv):
	# global
	serverUrl = ""
	login = ""
	pwd = ""
	getManager = False
	urlQueue = SetQueue(maxsize=5000)
	userIdsQueue = SetQueue(maxsize=5000)
	userInfosQueue = Queue(maxsize=5000)
	userManagerQueue = Queue(maxsize=5000)

	# signal handler
	signal.signal(signal.SIGINT, signal_handler)

	# retrive arguments
	try:
		opts, args = getopt.getopt(argv, "hs:u:p:m", ["help", "server=", "user=", "password=", "manager"])
		for opt, arg in opts:
			if opt in ("-h", "--help"):
				usage()
				sys.exit()
			elif opt in ("-s", "--server"):
				serverUrl = arg
			elif opt in ("-u", "--user"):
				login = arg
			elif opt in ("-p", "--password"):
				pwd = arg
			elif opt in ("-m", "--manager"):
				getManager = True
	except:
		usage()
		sys.exit()

	# threading get userinfo worker
	userIdWorker = []
	for i in range(10):
		w1 = Thread(target=getUserIdsWorker, args=(login, pwd, urlQueue, userIdsQueue,))
		w1.setDaemon(True)
		w1.start()
		userIdWorker.append(w1)

	# threading get relations worker
	userInfoWorker = []
	for i in range(20):
		w2 = Thread(target=getRelationsWorker, args=(serverUrl, login, pwd, userIdsQueue, userInfosQueue, getManager, userManagerQueue,))
		w2.setDaemon(True)
		w2.start()
		userInfoWorker.append(w2)

	# thread to print size of queue
	w3 = Thread(target=printStatusThread, args=(urlQueue, userIdsQueue, userInfosQueue, userManagerQueue,))
	w3.setDaemon(True)
	w3.start()

	# thread to write files
	w4 = Thread(target=writeFileThread, args=("users", "relations", userInfosQueue,))
	w4.setDaemon(True)
	w4.start()

	if getManager == True:
		w5 = Thread(target=writeManagerFileThread, args=("manager", userManagerQueue,))
		w5.setDaemon(True)
		w5.start()

	# build Queue url list
	MAX_TRY = 10
	essai = 0
	while essai < MAX_TRY:
		try:
			buildUrlSearchList(serverUrl, login, pwd, urlQueue)
		except KeyboardInterrupt:
			break
		except:
			essai += 1
			continue
		break

	while not (urlQueue.empty() and userIdsQueue.empty() and userInfosQueue.empty()):
		pass

	print ("end threads")
	urlQueue.put(None)
	userIdsQueue.put(None)
	userInfosQueue.put(None)

	# end of workers
	for i in userIdWorker:
		i.join()
	for i in userInfoWorker:
		i.join()

	time.sleep(5)

	sys.exit(0)


if __name__ == '__main__':
	main(sys.argv[1:])

