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

class metaWeblog:

	def __init__(self, endpoint, username, password):
		self.endpoint = endpoint
		self.username = username
		self.password = password
		return None

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

			# For Windows Live Spaces, an extra character is added and
			# must be removed.
			if postdate[-1] == 'Z':
				postdate = postdate[:-1].replace('-', '')

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

	def createPost(self, blogid, content, publish):
	
		rpcServer = xmlrpclib.ServerProxy(self.endpoint)
		
		"""
		content['title']
		content['description']
		content['mt_excerpt']
		content['mt_text_more']
		content['dateCreated']
		content['mt_keywords']
		content['mt_tb_ping_urls']
		content['mt_allow_comments']
		content['mt_allow_pings']
		content['mt_convert_breaks']
		content['categories']
		"""

		publish = xmlrpclib.Boolean(publish)
		# these categories are in the format expected by mt.setPostCategories
		# passing then to metaWeblog.newPos, that expects another format, can raise a exception
		categories = content.pop('categories')

		# Sanitize time for xmlrpc transport if needed.
		if content['dateCreated']:
			if isinstance(content['dateCreated'], xmlrpclib.DateTime) == False:
				content['dateCreated'] = xmlrpclib.DateTime(content['dateCreated'])
		try:
			result = rpcServer.metaWeblog.newPost(blogid, self.username, self.password, content, publish)
		except:
			# Some systems want an int instead of a boolean value. We'll assuage their
			# craziness for now.
			if publish == True:
				publish = 1
			else:
				publish = 0
			try:
				result = rpcServer.metaWeblog.newPost(blogid, self.username, self.password, content, publish)
			except Exception, e:
				raise Exception, str(e)
		

		# Try setting categories the MT way if the system requires it.
		# Create the categories using the movabletype format.
		try:
			rpcServer.mt.setPostCategories(result, self.username, self.password, categories)
		except Exception, e:
			print Exception, str(e)
			
		return result

	def editPost(self, postid, username, password, struct, publish):
	
		rpcServer = xmlrpclib.ServerProxy(self.endpoint)

		print postid
		
		try:
			repost = rpcServer.metaWeblog.editPost(postid, self.username, self.password, content, publish)

		except Exception, e:
			raise Exception, str(e)
			
		return postid

	def createPostWithCats(self, blogid, content, publish, cats):
	
		rpcServer = xmlrpclib.ServerProxy(self.endpoint)

		
		try:
			post = rpcServer.metaWeblog.newPost(blogid, self.username, self.password, content, publish)

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
			repost = rpcServer.metaWeblog.editPost(postid, self.username, self.password, content, publish)

			rpcServer.mt.setPostCategories(postid, self.username, self.password, cats)
		
		except Exception, e:
			raise Exception, str(e)
			
		return postid


	def repost(self, blogid, postid, content, publish):
	
		rpcServer = xmlrpclib.ServerProxy(self.endpoint)

		# Sanitize time for xmlrpc transport if needed.
		if isinstance(content['dateCreated'], xmlrpclib.DateTime) == False:
			content['dateCreated'] = xmlrpclib.DateTime(content['dateCreated'])
		
		try:
			repost = rpcServer.metaWeblog.editPost(postid, self.username, self.password, content, publish)
		
		except Exception, e:
			raise Exception, str(e)

		# Try setting categories the MT way if the system requires it.
		try:
			rpcServer.mt.setPostCategories(postid, self.username, self.password, content['categories'])
		except Exception, e:
			print Exception, str(e)
			
		return postid

	def getPost(self, postid):

		rpcServer = xmlrpclib.ServerProxy(self.endpoint)
		
		postList = []
		
		try:
			post = rpcServer.metaWeblog.getPost(postid, self.username, self.password)
		except Exception, e:
			raise Exception, str(e)
		
		return post

	def getCategoryList(self, blogid):

		rpcServer = xmlrpclib.ServerProxy(self.endpoint)

		try:
			cats = rpcServer.metaWeblog.getCategories(blogid, self.username, self.password)
		except Exception, e:
			raise Exception, str(e)


		cats2 = []
		for cat in cats:
			try:
				cat['categoryName']
			except:
				newDict = {'categoryName' : cat['title'],
				'categoryId' : cat['title']}
				cats2.append(newDict)

		if cats2 != []:
			cats = cats2

		return cats

	def getPostCats(self, blogid, postid):
		
		rpcServer = xmlrpclib.ServerProxy(self.endpoint)

		try:
			# There is no MetaWeblog-specific version of this function, so many blogging
			# systems appear to borrow from the MT API for this.
			catslist = rpcServer.mt.getPostCategories(postid, self.username, self.password)

		except Exception, e:
			raise Exception, str(e)

		return catslist

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
	
