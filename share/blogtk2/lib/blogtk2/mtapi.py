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

import xmlrpclib
import time
import string

class movabletype:

	def __init__(self, endpoint, username, password):
		self.endpoint = endpoint
		self.username = username
		self.password = password
	
	def getBlogs(self):
	
		# The use of an appkey has long since been deprecated, but what the
		# heck.
		appkey = "542ACD141588E5FEA3970055CF5796008A9063"
		
		rpcServer = xmlrpclib.ServerProxy(self.endpoint)
		
		blogList = []
		
		try:
			blogs = rpcServer.blogger.getUsersBlogs(appkey, self.username, self.password)
			
			for item in blogs:
				blogList.append([item['blogName'], item['blogid']])
				
		except Exception, e:
			raise Exception, str(e)
			
		return blogList
		
	def getPosts(self, blogid, count):

		rpcServer = xmlrpclib.ServerProxy(self.endpoint)
		
		try:
			posts = rpcServer.metaWeblog.getRecentPosts(str(blogid), self.username, self.password, count)

		except Exception, e:
			print Exception, str(e)
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

			title = entry['title']
			content = entry['description']
			postid = entry['postid']
			postdate = str(entry['dateCreated'])
			try:
				summary = entry['mt_excerpt']
			except:
				summary = ''
			try:
				extended = entry['mt_text_more']
			except:
				extended = ''	
			try:
				categories = entry['categories']
			except:
				try:
					cats_list = self.getPostCats(blogid, entry['postid'])
					categories = []
					for cat in cats_list:
						categories.append(cat['categoryName'])
				except:
					categories = ''
				
			feed = feed + '<entry>\n\
				<link href="' + postid +  '" rel="service.edit" title="" type="application/atom+xml"/>\n\
				<author>\n\
				<name>BloGTK Saved Listing</name>\n\
				</author>\n\
				<issued>' + postdate + '</issued>\n\
				<modified>' + postdate + '</modified>\n\
				<created>' + postdate + '</created>\n'

			try:
				for tag in entry['mt_keywords'].split(', '):
					# Strip any empty values from the keywords collection					
					if tag == '':
						pass
					else:
						feed = feed + ' <category scheme="" term="' + tag + '" />'
			except:
				pass

			try:
				for category in categories:
					feed = feed + '<category scheme="category" term="' + category + '" />'
			except:
				pass

			title_sanitized = self.sanitize_content(title)
			content_sanitized = self.sanitize_content(content)
			extended_sanitized = self.sanitize_content(extended)
			summary_sanitized = self.sanitize_content(summary)


			feed = feed + '<id>' + postid + '</id>\n\
				<title mode="escaped" type="text/html">' + title_sanitized + '</title>\n\
				<summary type="html" mode="escaped">' + summary_sanitized + '</summary>\n\
				<content type="html" xml:space="preserve">\n\
				' + content_sanitized + '\n\
				</content>\n\
				<content type="html" xml:space="preserve">\n\
				' + extended_sanitized + '\n\
				</content>\n\
				</entry>'
		feed = feed + '\n</feed>'		
			
		return feed
		
	def getPostTitles(self, blogid, count):
	
		rpcServer = xmlrpclib.ServerProxy(self.endpoint)
		
		postList = []
		
		try:
			posts = rpcServer.mt.getRecentPostTitles(blogid, self.username, self.password, str(count))
		except Exception, e:
			raise Exception, str(e)
		
		return posts
			
	def createPost(self, blogid, content, publish):
	
		rpcServer = xmlrpclib.ServerProxy(self.endpoint)
		
		"""
		content['title']
		content['description']
		content['dateCreated']
		content['mt_excerpt']
		content['mt_text_more'as]
		content['dateCreated']
		content['mt_keywords']
		content['mt_tb_ping_urls']
		content['mt_allow_comments']
		content['mt_allow_pings']
		content['mt_convert_breaks']
		content['categories']
		content['publish']
		"""

		# Sanitize time for xmlrpc transport if needed.
		if content['dateCreated']:
			if isinstance(content['dateCreated'], xmlrpclib.DateTime) == False:
				content['dateCreated'] = xmlrpclib.DateTime(content['dateCreated'])

		try:
			result = rpcServer.metaWeblog.newPost(blogid, self.username, self.password, content, content['publish'])
		
		except Exception, e:
			raise Exception, str(e)
			
		return result

	def createPostWithCats(self, blogid, content, publish, cats):
	
		rpcServer = xmlrpclib.ServerProxy(self.endpoint)

		# Sanitize time for xmlrpc transport if needed.
		if content['dateCreated']:
			if isinstance(content['dateCreated'], xmlrpclib.DateTime) == False:
				content['dateCreated'] = xmlrpclib.DateTime(content['dateCreated'])
		
		try:
			post = rpcServer.metaWeblog.newPost(blogid, self.username, self.password, content, content['publish'])

			rpcServer.mt.setPostCategories(post, self.username, self.password, cats)
		
		except Exception, e:
			raise Exception, str(e)
			
		return post

	def repostWithCats(self, blogid, postid, content, publish, cats):
	
		rpcServer = xmlrpclib.ServerProxy(self.endpoint)

		# Sanitize time for xmlrpc transport if needed.
		if content['dateCreated']:
			if isinstance(content['dateCreated'], xmlrpclib.DateTime) == False:
				content['dateCreated'] = xmlrpclib.DateTime(content['dateCreated'])
		
		try:
			repost = rpcServer.metaWeblog.editPost(postid, self.username, self.password, content, content['publish'])

			rpcServer.mt.setPostCategories(postid, self.username, self.password, cats)
		
		except Exception, e:
			raise Exception, str(e)
			
		return postid


	def getPostCats(self, blogid, postid):
		
		rpcServer = xmlrpclib.ServerProxy(self.endpoint)

		try:
			catslist = rpcServer.mt.getPostCategories(postid, self.username, self.password)

		except Exception, e:
			raise Exception, str(e)

		return catslist

	def getCategoryList(self, blogid):

		rpcServer = xmlrpclib.ServerProxy(self.endpoint)
		
		postList = []
		
		try:
			cats = rpcServer.mt.getCategoryList(blogid, self.username, self.password)
		except Exception, e:
			raise Exception, str(e)

		return cats

	def getPost(self, postid):

		rpcServer = xmlrpclib.ServerProxy(self.endpoint)
		
		postList = []
		
		try:
			post = rpcServer.metaWeblog.getPost(postid, self.username, self.password)
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
