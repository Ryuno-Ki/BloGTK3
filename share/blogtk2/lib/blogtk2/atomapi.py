#!/usr/bin/env python

# Copyright 2008 Jay Reding

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# 	http://www.apache.org/licenses/LICENSE-2.0
# 
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

try:
  from xml.etree import ElementTree # for Python 2.5 users
except:
  from elementtree import ElementTree

import time
import base64
#import sha
import hashlib
import httplib
import urllib2
import random

class AtomAPI:

	def __init__(self, user, password, app):

		self.user = user
		self.password = password
		self.app = app

	def getPosts(self, endpoint, blogid):
	
		if self.app == 'mt':
			self.getPostsMT(endpoint, blogid)

class MTAtom:
	
	def __init__(self, user, password, app):

		self.user = user
		self.password = password
		self.app = app

	def createDigest(self):
		self.nonce = base64.b64encode(hashlib.sha1(str(random.random())).digest())
		self.timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
		# <rant>http://www.robertprice.co.uk/robblog/archive/2005/2/WSSE_Authentication_For_Atom_Using_Perl.shtml
      # This is silly. Why decode the nonce for some, and not for others. This lack of standardization is unnecessary and annoying.
      # </rant>
		self.passwordDigest = base64.standard_b64encode(hashlib.sha1(base64.b64decode(self.nonce) + self.timestamp + self.password).digest())

	def getPosts(self, endpoint, blogid):

		self.createDigest()

		request = urllib2.Request(endpoint + '/' + blogid)
		request.add_header('WSSE profile', 'UsernameToken')
		request.add_header('X-WSSE', 'UsernameToken Username="' + self.user + '", PasswordDigest="' + self.passwordDigest + '", Created="' + self.timestamp + '", Nonce="' + self.nonce + '"')
		try:		
			f = urllib2.urlopen(request)
			result = f.read()
		except Exception, e:
			raise Exception, e

		print result

	def getPostsAsAtomFeed(self, blogid, count):

		pass

