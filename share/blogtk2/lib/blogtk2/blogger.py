# Copyright 2009 Jay Reding

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

import xmlrpclib
import time
import string

class Blogger:

	def __init__(self, endpoint, username, password):
		self.endpoint = endpoint
		self.username = username
		self.password = password
	
		# The use of an appkey has long since been deprecated, but what the
		# heck.
		self.appkey = "542ACD141588E5FEA3970055CF5796008A9063"
	
	def getBlogs(self):
		
		rpcServer = xmlrpclib.ServerProxy(self.endpoint)
		
		blogList = []
		
		try:
			blogs = rpcServer.blogger.getUsersBlogs(self.appkey, self.username, self.password)
			
			for item in blogs:
				blogList.append([item['blogName'], item['blogid']])
				
		except Exception, e:
			raise Exception, str(e)
			
		return blogList
		
	def getPosts(self, blogid, count):

		rpcServer = xmlrpclib.ServerProxy(self.endpoint)

		try:
			posts = rpcServer.blogger.getRecentPosts(self.appkey, blogid, self.username, self.password, count)

		except Exception, e:
			raise Exception, str(e)
			
		return posts

	def getPostsAsAtomFeed(self, blogid, count):

		response = self.getPosts(blogid, count)
		
		timestamp = time.strftime( "%Y-%m-%dT%H:%M:%S", time.gmtime())
			
		feed = '<?xml version="1.0" encoding="utf-8" standalone="yes"?>\n\
				<feed version="0.3" xml:lang="en-US">\n\
				<title mode="escaped" type="text/html">BloGTK Generated Feed</title>\n\
				<id>' + blogid + '</id>\n\
				<modified>' + timestamp + '</modified>\n\
				<generator url="http://blogtk.sourceforge.net/" version="2.0">BloGTK</generator>\n'
				
		entryArray = []	
		for entry in response:

			content = entry['content']
			postid = entry['postid']
			postdate = str(entry['dateCreated'])
				
			feed = feed + '<entry>\n\
				<link href="' + postid +  '" rel="service.edit" title="" type="application/atom+xml"/>\n\
				<author>\n\
				<name>BloGTK Saved Listing</name>\n\
				</author>\n\
				<issued>' + postdate + '</issued>\n\
				<modified>' + postdate + '</modified>\n\
				<created>' + postdate + '</created>\n'

			content_sanitized = self.sanitize_content(content)

			feed = feed + '<id>' + postid + '</id>\n\
				<title mode="escaped" type="text/html">' + postdate + '</title>\n\
				<summary type="html" mode="escaped"></summary>\n\
				<content type="html" xml:space="preserve">\n\
				' + content_sanitized + '\n\
				</content>\n\
				<content type="html" xml:space="preserve">\n\
				</content>\n\
				</entry>'
		feed = feed + '\n</feed>'		
			
		return feed
		
	def getPostTitles(self, blogid, count):
	
		response = self.getPosts(blogid, count)
		
		postList = []
		
		try:
			for date in str(entry['dateCreated']):
				postList.append(date)
		except Exception, e:
			raise Exception, str(e)
		
		return postList
			
	def createPost(self, blogid, content, publish):
	
		rpcServer = xmlrpclib.ServerProxy(self.endpoint)
		
		"""
		content['content']
		content['dateCreated']
		"""

		# Sanitize time for xmlrpc transport if needed.
		if content['dateCreated']:
			if isinstance(content['dateCreated'], xmlrpclib.DateTime) == False:
				content['dateCreated'] = xmlrpclib.DateTime(content['dateCreated'])

		try:
			result = rpcServer.blogger.newPost(self.appkey, blogid, self.username, self.password, content['content'], publish)
		
		except Exception, e:
			raise Exception, str(e)
			
		return result

	def repost(self, blogid, postID, content, publish):

		rpcServer = xmlrpclib.ServerProxy(self.endpoint)

		if content['dateCreated']:
			if isinstance(content['dateCreated'], xmlrpclib.DateTime) == False:
				content['dateCreated'] = xmlrpclib.DateTime(content['dateCreated'])

		try:
			result = rpcServer.blogger.editPost(self.appkey, postID, self.username, self.password, content['content'],publish)

		except Exception, e:
			raise Exception, str(e)
			
		return postID

	def getPost(self, postid):

		rpcServer = xmlrpclib.ServerProxy(self.endpoint)
		
		postList = []
		
		try:
			post = rpcServer.blogger.getPost(self.appkey, postid, self.username, self.password)
		except Exception, e:
			raise Exception, str(e)
		
		return post

	def deletePost(self, postid):

		rpcServer = xmlrpclib.ServerProxy(self.endpoint)

		try:
			postDelete = rpcServer.blogger.deletePost('', postid, self.username, self.password, True)
		except:
			raise Exception, str(e)

		return postDelete

	# Generic Functions
	#-------------------------------------------
	def sanitize_content(self, content):

		no_amps = string.replace(content, '&', '&amp;')
		no_lts = string.replace(no_amps, '<', '&lt;')
		sanitized = string.replace(no_lts, '>', '&gt;')

		return sanitized
