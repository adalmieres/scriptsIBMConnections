#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# dépendances
import requests
import xml.dom.minidom
import sys
import signal
import os
import getopt
import logging
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

# fonction de création des url de recherche qui sont ensuite ajouté à la queue qin
def getUrlSearchList(server, login, pwd, qin):
	url = server + "/search/atom/mysearch?scope=forums&constraint=%7B%22type%22%3A%22category%22%2C%22values%22%3A%5B%22Person%2FC6C42798-EC4D-427D-9070-FF4BB770D360%02KLEIN+Gilles%22%5D%7D" + '&ps=150'
	dom = getAtomFeed(url, login, pwd)
	totalResult = dom.getElementsByTagName('opensearch:totalResults')[0]
	logging.info(str(totalResult))
	totalResult = int(totalResult.firstChild.data)
	if totalResult > 150:
		nbPage = int(float(totalResult) / 150) + 1
		for n in range(1,nbPage,1):
			item = url + "&page=" + str(n) 
			qin.put(item)
			logging.debug(item)
	else:
		nbPage = 1
		qin.put(url)
		logging.debug(url)
	
# fonction de récupération des liens vers le document atom des topics à partir d'une url de recherche présent dans qin
def getTopicLink(login, pwd, qin, qout):
	while True:
		url = qin.get()
		sys.stdout.write(str(url))
		sys.stdout.flush()
		if url == None:
			break
		qin.task_done()
		try:
			dom = getAtomFeed(url, login, pwd) #on récupère le résultat de recherche
		except:
			continue
			
		# on va chercher tous les liens vers les documents atom de type forum
		feed = dom.firstChild
		entries = feed.getElementsByTagName('entry')
		for entry in entries :
			link = entry.getElementsByTagName('link')[1]
			logging.debug(str(link))
			qout.put(link)
	
#def getRecommendationLink(server, login, pwd, qin, qout):

#def postRecommendation(server, login, pwd, qin):

def printStatusThread(q0, q1):
	strtime = time.time()
	while True:
		sys.stdout.write('\r\x1b[K')
		sys.stdout.write("urls:" + str(q0.qsize()) + " | ")
		sys.stdout.write("links:" + str(q1.qsize()) + " | ")
		sys.stdout.flush()
		time.sleep(1)

def main(argv):
	# set du logger
	logging.basicConfig(level=logging.DEBUG, format='%(relativeCreated)6d %(threadName)s %(message)s')

	# global
	serverUrl = ""
	login = ""
	pwd = ""
	urlQueue = SetQueue(maxsize=5000)
	topicQueue = SetQueue(maxsize=5000)

	# signal handler
	signal.signal(signal.SIGINT, signal_handler)

	# retrive arguments
	try:
		opts, args = getopt.getopt(argv, "hs:u:p:m", ["help", "server=", "user=", "password="])
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

	# threading get userinfo worker, le worker fonctionne ensuite tout seul
	topicUrlWorker = []
	for i in range(10):
		logging.debug("start topicUrlWorker")
		w1 = Thread(target=getTopicLink, args=(login, pwd, urlQueue, topicQueue,))
		w1.setDaemon(True)
		w1.start()
		topicUrlWorker.append(w1)
		
	# thread to print size of queue
	#w3 = Thread(target=printStatusThread, args=(urlQueue, topicQueue,))
	#w3.setDaemon(True)
	#w3.start()
		
	# build Queue url list
	MAX_TRY = 10
	essai = 0
	while essai < MAX_TRY:
		try:
			logging.debug("get list of search page url")
			getUrlSearchList(serverUrl, login, pwd, urlQueue)
			logging.debug(str(urlQueue.qsize()))
		except KeyboardInterrupt:
			logging.info("interrupt")
			break
		except:
			essai += 1
			logging.warn("error while getUrlSearchList")
			continue
		break

	while not (urlQueue.empty() and topicQueue.empty()):
		pass

	print ("end threads")
	urlQueue.put(None)
	topicQueue.put(None)

	# end of workers
	for i in topicUrlWorker:
		i.join()

	time.sleep(5)

	sys.exit(0)

if __name__ == '__main__':
	main(sys.argv[1:])
