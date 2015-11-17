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
if os.name != "nt":
	import curses

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
	curses.endwin()
	sys.exit(0)

def usage():
	"""usage de la ligne de commande"""
	print ("usage : " + sys.argv[0] + "-h --help -s --server someurl.com -u --user login -p --password password")
	sys.exit(0)

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


def getProfileWorker(server, login, pwd, qin, qout):
	while True:
		userid = qin.get()
		if userid == None:
			break
		qin.task_done()
		url = server + '/profiles/atom/profile.do?userid=' + userid
		try:
			dom = getAtomFeed(url, login, pwd)
		except:
			continue
		feed = dom.firstChild
		links = feed.getElementsByTagName('link')
		for link in links:
			href = link.attributes["href"].value
			if href.find("targetKey=") >= 0:
				start = href.find("targetKey=") + 10
				end = start + 36
				qout.put(str(href[start:end]))

def getTagsWorker(server, login, pwd, qin, qout):
	while True:
		targetKey = qin.get()
		if targetKey == None:
			break
		qin.task_done()
		url = server + '/profiles/atom/profileTags.do?targetKey=' + targetKey
		try:
			dom = getAtomFeed(url, login, pwd)
		except:
			continue
		feed = dom.firstChild
		tags = feed.getElementsByTagName('atom:category')
		for tag in tags:
			term = str(tag.attributes["term"].value)
			freq = int(tag.attributes["snx:frequency"].value)
			for i in range(0,freq):
				qout.put(term)

def printStatusThread(screen, q0, q1, q2, q3):
	strtime = time.time()
	while True:
		elapsed = time.time() - strtime
		screen.clear()
		screen.addstr(0,20,time.strftime("%H:%M:%S", time.gmtime(elapsed)))
		screen.addstr(0,0,"url Queue : " + str(q0.qsize()))
		screen.addstr(1,0,"userId Queue : " + str(q1.qsize()))
		screen.addstr(2,0,"user info Queue : " + str(q2.qsize()))
		screen.addstr(3,0,"user manager Queue : " + str(q3.qsize()))
		screen.refresh()
		time.sleep(1)

def writeFileThread(tagsFilename, qin):
	# file for user details
	t = open(tagsFilename + ".csv", "w")
	while True:
		data = qin.get()
		# write data
		t.write(data + "\n")
		qin.task_done()

def main(argv):
	# global
	serverUrl = ""
	login = ""
	pwd = ""
	getManager = False
	urlQueue = SetQueue(maxsize=5000)
	userIdsQueue = SetQueue(maxsize=10000)
	userTargetQueue = Queue(maxsize=5000)
	userTagsQueue = Queue(maxsize=5000)

	#curse
	if os.name != "nt":
		stdscr = curses.initscr()
		curses.noecho()
		curses.cbreak()
		stdscr.clear()

	# signal handler
	signal.signal(signal.SIGINT, signal_handler)

	# retrive arguments
	try:
		opts, args = getopt.getopt(argv, "hs:u:p:m", ["help", "server=", "user=", "password="])
		if len(argv) == 0:
			usage()
			sys.exit(0)
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
	except:
		usage()
		sys.exit()

	# threading get userinfo worker
	workers = []
	for i in range(10):
		w = Thread(target=getUserIdsWorker, args=(login, pwd, urlQueue, userIdsQueue,))
		w.setDaemon(True)
		w.start()
		workers.append(w)

	# threading get targetKey worker
	for i in range(5):
		w = Thread(target=getProfileWorker, args=(serverUrl, login, pwd, userIdsQueue, userTargetQueue,))
		w.setDaemon(True)
		w.start()
		workers.append(w)
		
	# threading get tags worker
	for i in range(5):
		w = Thread(target=getTagsWorker, args=(serverUrl, login, pwd, userTargetQueue, userTagsQueue,))
		w.setDaemon(True)
		w.start()
		workers.append(w)

	# thread to print size of queue
	if os.name != "nt":
		w = Thread(target=printStatusThread, args=(stdscr, urlQueue, userIdsQueue, userTargetQueue, userTagsQueue,))
		w.setDaemon(True)
		w.start()
		workers.append(w)

	# thread to write files
	w = Thread(target=writeFileThread, args=("tags", userTagsQueue,))
	w.setDaemon(True)
	w.start()
	workers.append(w)

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

	time.sleep(1)
		
	while not (urlQueue.empty() and userIdsQueue.empty() and userTargetQueue.empty() and userTagsQueue.empty()):
		print("url : " + str(urlQueue.qsize()))
		print("ids : " + str(userIdsQueue.qsize()))
		print("target : " + str(userTargetQueue.qsize()))
		print("tags : " + str(userTagsQueue.qsize()))
		time.sleep(1)

	print ("end threads")
	urlQueue.put(None)
	userIdsQueue.put(None)
	userInfosQueue.put(None)

	# end of workers
	for i in userIdWorker:
		i.join()
	for i in userInfoWorker:
		i.join()

	w3.join()
	w4.join()
	w5.join()

	if os.name != "nt":
		curses.endwin()

	sys.exit(0)


if __name__ == '__main__':
	main(sys.argv[1:])

