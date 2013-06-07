# Copyright (C) 2007 Google Inc.
# Copyright (C) 2009 Jay Reding
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
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

from gdata import service
import gdata
import atom
import getopt
import sys
import time
import string

import feedparser


class BloggerAtom:

	def __init__(self, email, password):

		# Authenticate using ClientLogin.
		self.service = service.GDataService(email, password)
		self.service.source = 'BloGTK-2.0'
		self.service.service = 'blogger'
		self.service.server = 'www.blogger.com'
		self.service.ProgrammaticLogin()

	def getPostsAsAtomFeed(self, blogid, num):

		# Request the feed.
		blogger_feed = self.service.GetFeed('/feeds/' + blogid + '/posts/default')

		timestamp = time.strftime( "%Y-%m-%dT%H:%M:%S", time.gmtime())

		feed = '<?xml version="1.0" encoding="utf-8" standalone="yes"?>\n\
			<feed version="0.3" xml:lang="en-US">\n\
			<title mode="escaped" type="text/html">BloGTK Generated Feed</title>\n\
			<id>' + blogid + '</id>\n\
			<modified>' + timestamp + '</modified>\n\
			<generator url="http://blogtk.sourceforge.net/" version="2.0">BloGTK</generator>\n'

		for entry in blogger_feed.entry:
			postdate = entry.published.text[:19].replace('-', '')
			postid = entry.id.text.split('-')[-1]
			content = entry.content.text
			title = entry.title.text
				
			feed = feed + '<entry>\n\
				<link href="' + postid +  '" rel="service.edit" title="BloGTK Cache" type="application/atom+xml"/>\n\
				<author>\n\
				<name>BloGTK Saved Listing</name>\n\
				</author>\n\
				<issued>' + postdate + '</issued>\n\
				<modified>' + postdate + '</modified>\n\
				<created>' + postdate + '</created>\n'


			# Make entry text XML safe. Yes, this is a kludge - any better ideas
			if title:
				title_sanitized = self.sanitize_content(title)
			else:
				title_sanitized = ' '
			content_sanitized = self.sanitize_content(content)

			feed = feed + '<id>' + postid + '</id>\n\
				<title mode="escaped" type="html">' + title_sanitized + '</title>\n\
				<content type="html" xml:space="preserve">\n\
				' + content_sanitized + '\n\
				</content>\n\
				</entry>'
		feed = feed + '\n</feed>'		

		# Print the results.
		return feed

	def getIndividualPost(self, blogID, postID):

		# Create query and submit a request.
		query = service.Query()
		query.feed = '/feeds/' + blogID + '/posts/default/' + postID
		feed = self.service.Get(query.ToUri())

		return feed

	def createPost(self, blogID, title, content, author_name, is_draft, timestamp=None):
		"""This method creates a new post on a blog.  The new post can be stored as
		a draft or published based on the value of the is_draft parameter.  The
		method creates an GDataEntry for the new post using the title, content,
		author_name and is_draft parameters.  With is_draft, True saves the post as
		a draft, while False publishes the post.  Then it uses the given
		GDataService to insert the new post.  If the insertion is successful, the
		added post (GDataEntry) will be returned.
		"""

		# Create the entry to insert.
		entry = gdata.GDataEntry()
		entry.author.append(atom.Author(atom.Name(text='Post author')))
		entry.title = atom.Title('xhtml', text=title)
		entry.content = atom.Content('html', text=content)
		if is_draft:
			control = atom.Control()
			control.draft = atom.Draft(text='yes')
			entry.control = control

		# If a timestamp is specified, use that timestamp
		if timestamp:
			entry.published = atom.Published(timestamp)

		# Ask the service to insert the new entry.
		return self.service.Post(entry, 
			'/feeds/' + blogID + '/posts/default')

	def editPost(self, blogID, postID, title, content, author_name, is_draft, timestamp=None):
		
		# Create the entry to insert.
		entry = gdata.GDataEntry()
		entry.author.append(atom.Author(atom.Name(text='Post author')))
		entry.title = atom.Title('xhtml', text=title)
		entry.content = atom.Content('html', text=content)
		if is_draft:
			control = atom.Control()
			control.draft = atom.Draft(text='yes')
			entry.control = control

		# If a timestamp is specified, use that timestamp
		if timestamp:
			entry.published = atom.Published(timestamp)

		# Ask the service to insert the new entry.
		return self.service.Put(entry, 
			'/feeds/' + blogID + '/posts/default/' + postID)

	def deletePost(self, blogID, postID):
		self.service.Delete('/feeds/' + blogID + '/posts/default/' + postID)

	# Generic Functions
	#-------------------------------------------
	def sanitize_content(self, content):

		no_amps = string.replace(content, '&', '&amp;')
		no_lts = string.replace(no_amps, '<', '&lt;')
		sanitized = string.replace(no_lts, '>', '&gt;')

		return sanitized


