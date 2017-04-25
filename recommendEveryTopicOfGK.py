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



def main(argv):
	# global
	serverUrl = ""
	login = ""
	pwd = ""
	urlQueue = SetQueue(maxsize=5000)
	TopicQueue = SetQueue(maxsize=5000)

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
	except:
		usage()
		sys.exit()

    # Get search reseults
    # example : https://collaboratif.covea.fr/search/atom/mysearch?scope=forums&constraint={"type":"category","values":["Person/C6C42798-EC4D-427D-9070-FF4BB770D360%02KLEIN%20Gilles"]}

    url = "https://collaboratif.covea.fr/search/atom/mysearch?scope=forums&constraint=%7B%22type%22%3A%22category%22%2C%22values%22%3A%5B%22Person%2FC6C42798-EC4D-427D-9070-FF4BB770D360%02KLEIN+Gilles%22%5D%7D"
    dom = getAtomFeed(url,login,pwd)
    print(dom.toxml())

    # threading getTopicQue




if __name__ == '__main__':
	main(sys.argv[1:])
