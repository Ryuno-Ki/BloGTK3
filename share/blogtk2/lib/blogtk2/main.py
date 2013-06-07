#!/usr/bin/python

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

try:
  from xml.etree import ElementTree # for Python 2.5 users
except:
  from elementtree import ElementTree

from gdata import service
import gdata
import atom
import os
import base64

import time
import threading

import gtk
import gtk.glade
import gnome.ui
import gobject
import webkit

import webbrowser
import feedparser

# Internal Libraries
import config
import editor
import firstrun

import mtapi
import bloggeratom
import atomapi
import metaweblog
import blogger

from blogtk2 import SHARED_FILES

def threaded(f):
    def wrapper(*args):
        t = threading.Thread(target=f, args=args)
        t.start()
    return wrapper

class BloGTK:

	def __init__(self):

		program = gnome.init('blogtk', '2.0')

		self.glade = gtk.glade.XML(os.path.join(SHARED_FILES, 'glade', 'blogtk2.glade'))

		self.winMain = self.glade.get_widget('winMain')
		self.tvBlogs = self.glade.get_widget('tvBlogs')
		self.tvPosts = self.glade.get_widget('tvPosts')

		self.appbar = self.glade.get_widget('appbarMain')	

		self.swPreview = self.glade.get_widget('swPreview')

		self.dlgAbout = self.glade.get_widget('dlgAbout')

		# Create preview
		self.html_Preview = webkit.WebView()
		# We want to lock down our preview to prevent scripting and plugins
		# from doing anything.

		self.webkit_settings = webkit.WebSettings()
		self.webkit_settings.set_property("enable-plugins", False)
		self.webkit_settings.set_property("enable-scripts", False)

		self.html_Preview.set_settings(self.webkit_settings)
		self.setWelcome()

		self.winMain.show()

		# Main Window events
		self.winMain.connect('delete_event', self.delete_event)
		self.winMain.connect('destroy', self.destroy)

		dic = { 'on_tbtnRefresh_clicked' : self.refreshPosts,
			'on_tvPosts_row_activated' : self.sendPostToEditor,
			'gtk_main_quit' : self.destroy,
			'on_tbtnHome_clicked' : self.goToBlogHome,
			'on_tbtnEdit_clicked' : self.sendPostToEditor,
			'on_mniEditPost_activate' : self.sendPostToEditor,
			'on_tbtnNew_clicked' : self.createNewPost,
			'on_mniNewPost_activate' : self.createNewPost,
			'on_tvBlogs_row_activated' : self.createNewPost,
			'on_tbtnDelete_clicked' : self.deletePost,
			'on_mniDeletePost_activate' : self.deletePost,
			'on_tbtnAccounts_clicked' : self.initAccounts,
			'on_mniPrefs_activate' : self.initAccounts,
			'on_mniOffline_activate' : self.goOffline,
			'on_mniDisplayAbout_activate' : self.displayAbout,
			'on_mniMainQuit_activate' : self.closeMainWin,
			'on_dlgAbout_close' : self.windowHider
		 }
		self.glade.signal_autoconnect(dic)

		self.tbtnRefresh = self.glade.get_widget('tbtnRefresh')
		self.mniOffline = self.glade.get_widget('mniOffline')

		# This needs to be replaced with a variable
		self.homeDir = os.path.expanduser('~')
		self.configDir = self.homeDir + "/.BloGTK"

		self.firstrun = firstrun.BloGTKFirstRun(self)
		self.firstrun.checkConfigStatus()

		# For offline support, we need a flag to note whether we should go offline or not.
		self.isOffline = False

		# We need a change flag here to prevent the app from closing
		# if the editor has unsaved changes.
		self.changeFlag = False

		# Create our accelerator group
		self.accelGroup = gtk.AccelGroup()
		self.winMain.add_accel_group(self.accelGroup)
		self.addAccelerators()

	def addAccelerators(self):
		# Here is where we create our accelerators for various actions.
		# Menubar actions
		mniNewPost = self.glade.get_widget('mniNewPost')
		key, mod = gtk.accelerator_parse("<Control>N")
		mniNewPost.add_accelerator("activate", self.accelGroup, key, mod, gtk.ACCEL_VISIBLE)

		mniEditPost = self.glade.get_widget('mniEditPost')
		key, mod = gtk.accelerator_parse("<Control>E")
		mniEditPost.add_accelerator("activate", self.accelGroup, key, mod, gtk.ACCEL_VISIBLE)

		mniDeletePost = self.glade.get_widget('mniDeletePost')
		key, mod = gtk.accelerator_parse("<Control>D")
		mniDeletePost.add_accelerator("activate", self.accelGroup, key, mod, gtk.ACCEL_VISIBLE)

		mniPrefs = self.glade.get_widget('mniPrefs')
		key, mod = gtk.accelerator_parse("<Control>S")
		mniPrefs.add_accelerator("activate", self.accelGroup, key, mod, gtk.ACCEL_VISIBLE)

		mniDisplayAbout = self.glade.get_widget('mniDisplayAbout')
		key, mod = gtk.accelerator_parse("<Control>A")
		mniDisplayAbout.add_accelerator("activate", self.accelGroup, key, mod, gtk.ACCEL_VISIBLE)

		# Toolbar actions
		
		key, mod = gtk.accelerator_parse("F5")
		self.tbtnRefresh.add_accelerator("clicked", self.accelGroup, key, mod, gtk.ACCEL_VISIBLE)

		tbtnHome = self.glade.get_widget('tbtnHome')
		key, mod = gtk.accelerator_parse("<Control>H")
		tbtnHome.add_accelerator("clicked", self.accelGroup, key, mod, gtk.ACCEL_VISIBLE)


	def initBlogList(self):

		self.accountArray = self.configReader.getConfigArray()

		self.model = gtk.TreeStore(gobject.TYPE_STRING, gobject.TYPE_STRING)
		self.tvBlogs.set_model(self.model)
		self.tvBlogs.set_headers_visible(True)

		column = gtk.TreeViewColumn("Blog",gtk.CellRendererText(), text=0)
		self.idColumn = gtk.TreeViewColumn("ID", gtk.CellRendererText(), text=0)
		self.idColumn.set_visible(False)
		column.set_resizable(True)
		self.tvBlogs.append_column(column)
		self.tvBlogs.append_column(self.idColumn)

		self.tvBlogs.show()   

		for account in self.accountArray:
			self.model.append(None, [account['name'], account['endpoint'] + '/' + account['id']])

		# Now it's be a Calvinist and predestinate our default selection in the
		# TreeView.
		sel = self.tvBlogs.get_selection()
		sel.set_mode(gtk.SELECTION_SINGLE)

		sel.select_path(0)	
		self.tvBlogs.set_cursor(0, None, False )

		self.tvBlogs.connect('cursor_changed', self.checkListing)

	def initPostList(self):

		self.postsModel = gtk.TreeStore(gobject.TYPE_STRING, gobject.TYPE_STRING, gobject.TYPE_STRING)
		self.tvPosts.set_model(self.postsModel)
		self.tvPosts.set_headers_visible(True)
		renderer1 = gtk.CellRendererText()
		renderer2 = gtk.CellRendererText()
		self.postIdColumn = gtk.TreeViewColumn("Post ID",renderer1, text=0)
		self.postIdColumn.set_resizable(True)
		self.postTitleColumn = gtk.TreeViewColumn("Post Title", gtk.CellRendererText(), text=1)
		self.postTitleColumn.set_resizable(True)
		self.postDateColumn = gtk.TreeViewColumn("Post Date", renderer2, text=2)
		self.tvPosts.append_column(self.postIdColumn)
		self.tvPosts.append_column(self.postTitleColumn)
		self.tvPosts.append_column(self.postDateColumn)

		# Now it's be a Calvinist and predestinate our default selection in the
		# TreeView.
		sel = self.tvPosts.get_selection()
		sel.set_mode(gtk.SELECTION_SINGLE)

		sel.select_path(0)	
		#self.tvPosts.set_cursor(0, None, False)

		self.tvPosts.connect('cursor_changed', self.createPreview)

		self.checkListing(None)

	def initAccounts(self, widget, data=None):

		config.ConfigGUI(self)

	def main(self):

		# Initialize our config reader class	
		self.configReader = config.ConfigReader()

		# Initialize our config writer class
		self.configWriter = config.ConfigWriter()

		# Initialize the blog listing.
		self.initBlogList()

		# Initialize the post listing
		self.initPostList()

		self.tvBlogs.connect('cursor_changed', self.checkListing)

	@threaded
	def refreshPosts(self, widget):
	
		selected_iter = self.tvBlogs.get_selection().get_selected()[1]
		accountName = self.model.get_value(selected_iter, 0)

		for account in self.accountArray:
			if account['name'] == accountName:
				thisAccount = account

		self.appbar.push(_('Getting posts'))

		# Make it so the user cannot hit Refresh again while refresh is cylcling.
		self.tbtnRefresh.set_sensitive(False)

		gtk.gdk.threads_enter()
		self.timeout_handler_id = gobject.timeout_add(100, self.update_progress_bar, 'live', 0)   
		gtk.gdk.threads_leave()

		# SYSTEM DEPENDENT
		try:
			if thisAccount['api'] == "mt":
				mt = mtapi.movabletype(thisAccount['endpoint'], thisAccount['username'], thisAccount['password'])
				posts = mt.getPostsAsAtomFeed(thisAccount['id'], thisAccount['pullcount'])
				self.savePostsToCache(posts)

				# We also refresh the categories here
				cats = mt.getCategoryList(thisAccount['id'])
				self.configWriter.writeCategoryArray(thisAccount['name'], cats)

			elif thisAccount['api'] == 'mtatom':
				mtatom = atomapi.MTAtom(thisAccount['endpoint'], thisAccount['username'], thisAccount['password'])			
				mtatom = mt.getPostsAsAtomFeed(thisAccount['id'], thisAccount['pullcount'])

			elif thisAccount['api'] == 'gdata':
				bloggergdata = bloggeratom.BloggerAtom(thisAccount['username'], thisAccount['password'])
				posts = bloggergdata.getPostsAsAtomFeed(thisAccount['id'], thisAccount['pullcount'])

				self.savePostsToCache(posts)

			elif thisAccount['api'] == 'metaweblog':
				mw = metaweblog.metaWeblog(thisAccount['endpoint'], thisAccount['username'], thisAccount['password'])
				posts = mw.getPostsAsAtomFeed(thisAccount['id'], thisAccount['pullcount'])
				self.savePostsToCache(posts)

				# We also refresh the categories here
				try:
					cats = mw.getCategoryList(thisAccount['id'])
					self.configWriter.writeCategoryArray(thisAccount['name'], cats)
				except Exception, e:
					print Exception, str(e)

			elif thisAccount['api'] == 'blogger':
				bloggerapi = blogger.Blogger(thisAccount['endpoint'], thisAccount['username'], thisAccount['password'])
				posts = bloggerapi.getPostsAsAtomFeed(thisAccount['id'], thisAccount['pullcount'])

				self.savePostsToCache(posts)
					
			else:
				pass

			self.timeout_handler_id2 = gobject.timeout_add(100, self.update_progress_bar, 'die', 0)
			self.appbar.push(_('Retrieved List of Posts'))

			self.tbtnRefresh.set_sensitive(True)

		except Exception, e:
			self.timeout_handler_id2 = gobject.timeout_add(100, self.update_progress_bar, 'die', 0)

			self.appbar.push('Error: ' + str(Exception) + ' ' + str(e))

			print str(Exception), str(e)
		
			self.tbtnRefresh.set_sensitive(True)


	def savePostsToCache(self, posts):

		self.postsModel.clear()

		parsedPosts = feedparser.parse(posts)

		for entry in parsedPosts.entries:
			title =  entry.title
			dateArray = entry.issued_parsed
			dateString = str(dateArray[0]) + "," + str(dateArray[1]) + "," + str(dateArray[2]) + "," + str(dateArray[3]) + "," + str(dateArray[4]) + "," + str(dateArray[5])
			date2 = time.strptime(dateString, '%Y,%m,%d,%H,%M,%S')
			date = time.strftime('%x %X', date2)
			id = entry.links[0].href
			iter = self.postsModel.append(None, [id, title, date])

		print _('Saving posts to cache.')

		selected_iter = self.tvBlogs.get_selection().get_selected()[1]
		accountID = self.model.get_value(selected_iter, 1)

		self.postsTempFile = self.configDir + '/cache/' + base64.b64encode(accountID) + ".xml"

		f = open(self.postsTempFile,'w')
		f.write(str(posts))
		f.close()


	def update_progress_bar(self, mortality, foo):

 		if mortality == 'live':
			self.appbar.get_progress().pulse()
			return True
		if mortality == 'die':
			gobject.source_remove(self.timeout_handler_id)
			self.appbar.get_progress().set_fraction(0.0)
			return False
		

	def goToBlogHome(self, widget):
		selected_iter = self.tvBlogs.get_selection().get_selected()[1]
		accountName = self.model.get_value(selected_iter, 0)
		for account in self.accountArray:
			if account['name'] == accountName:
				uri = account['uri']

		webbrowser.open(uri)

	def setWelcome(self):
		self.html_Preview.load_html_string(_('<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">\
         <html xmlns="http://www.w3.org/1999/xhtml">\
         <head>\
			 <title>Welcome To BloGTK</title>\
         <meta http-equiv="Content-Type" content="text/html; charset=iso-8859-1" />\
         </head>\
         <body>\
         <div style="border-bottom: 1px solid #000; padding: 5px;"><h1 style="margin: 0; padding: 0;">Welcome to BloGTK 2</h1></div>\
         <p>Welcome to BloGTK, the premiere blogging client for Linux. BloGTK allows you to manage, edit, \
         and manipulate posts across a wide range of weblogging systems.</p>\
			<p>To learn more about BloGTK, <a href="http://blogtk.jayreding.com/">visit the official BloGTK website</a>\
			for helpful information on using BloGTK.</p>\
         </body>\
         </html>'), 'file:///')
		self.swPreview.add(self.html_Preview)
		self.html_Preview.show()


	def checkListing(self, widget):

		self.postsModel.clear()

		selected_iter = self.tvBlogs.get_selection().get_selected()[1]
		accountID = self.model.get_value(selected_iter, 1)
		accountName = self.model.get_value(selected_iter, 0)

		# We need to get the account type to change the display for Blogger feeds, which use the post URI instead of the numeric ID
		for account in self.accountArray:
			if account['name'] == accountName:
				api = account['api']	

		if os.path.isfile(self.configDir + "/cache/" + base64.b64encode(accountID) + ".xml"):

			self.postsModel.clear()
			f = open(self.configDir + "/cache/" + base64.b64encode(accountID) + ".xml", "r")
			parser = feedparser.parse(f)
				
			for entry in parser.entries:
				title =  entry.title
				dateArray = entry.issued_parsed
				dateString = str(dateArray[0]) + "," + str(dateArray[1]) + "," + str(dateArray[2]) + "," + str(dateArray[3]) + "," + str(dateArray[4]) + "," + str(dateArray[5])
				date2 = time.strptime(dateString, '%Y,%m,%d,%H,%M,%S')
				date = time.strftime('%x %X', date2)
				id = entry.links[0].href
				iter = self.postsModel.append(None, [id, title, date])
						
		else:
			self.appbar.push(_('Click refresh on toolbar to retrieve list of recent posts'))

	def createPreview(self, widget):

		selected_iter = self.tvBlogs.get_selection().get_selected()[1]
		accountID = self.model.get_value(selected_iter, 1)
		
		selected_iter2 = self.tvPosts.get_selection().get_selected()[1]
		postTitle = self.tvPosts.get_model().get_value(selected_iter2, 1)
		postId = self.tvPosts.get_model().get_value(selected_iter2, 0)
		postDate = self.tvPosts.get_model().get_value(selected_iter2, 2)

		if os.path.isfile(self.configDir + "/cache/" + base64.b64encode(accountID) + ".xml"):
			f = open(self.configDir + "/cache/" + base64.b64encode(accountID) + ".xml")
			feed = ElementTree.parse(self.configDir + '/cache/' + base64.b64encode(accountID) + '.xml').getroot()

			for entry in feed.findall('entry'):
				
				if entry.find('link').attrib['href'] == postId:
					title = entry.find('title').text
					content = entry.findall('content')[0].text
					post_datestamp = time.strptime(entry.find('issued').text, '%Y%m%dT%H:%M:%S')
					postDate = time.strftime('%x %X', post_datestamp)
					tags = []
					cats = []
					if len(entry.findall('category')) != 0:
						for index, tag in enumerate(entry.findall('category')):
							if tag.attrib['scheme'] == 'category':
								cats.append(tag.attrib['term'])
							else:
								 tags.append(tag.attrib['term'])

			preview_string = _('<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">\
			<html xmlns="http://www.w3.org/1999/xhtml">\
			<head>\
			<meta http-equiv="Content-Type" content="text/html; charset=utf-8" />\
			<title>' + title + '</title>\
			</head>\
			<body>\
			<div style="border-bottom: 1px solid #000; padding: 5px;"><h2 style="margin: 0; padding: 0;">' + title + '</h2><br /><strong>Posted: ' + postDate+ '</strong><p>')


			if len(tags) != 0:
				tag_string = ''
				for index, tag in enumerate(tags):
					if index != (len(tags) - 1):
						tag_string = tag_string + tag + ', '
					else:
						tag_string = tag_string + tag
					
				preview_string = preview_string + _('<strong>Post Tags:&nbsp;</strong> ') + tag_string + '<br />'

			if len(cats) != 0:
				cat_string = ''
				for index, cat in enumerate(cats):
					if index != (len(cats) - 1):
						cat_string = cat_string + cat + ', '
					else:
						cat_string = cat_string + cat
					
				preview_string = preview_string + _('<strong>Post Categories:&nbsp;</strong> ') + cat_string + '<br />'
			preview_string = preview_string + '</p></div>\
			' + content + '\
			</body>\
			</html>'

					
			self.html_Preview.load_html_string(preview_string, 'file:///')
		

		else:
			print _('No cache file found.')

	def refreshBlogList(self):

		self.configReader = config.ConfigReader()

		self.accountArray = self.configReader.getConfigArray()

		self.model.clear()

		for account in self.accountArray:
			self.model.append(None, [account['name'], account['endpoint'] + '/' + account['id']])

		# Now it's be a Calvinist and predestinate our default selection in the
		# TreeView.
		sel = self.tvBlogs.get_selection()
		sel.set_mode(gtk.SELECTION_SINGLE)

		sel.select_path(0)	
		self.tvBlogs.set_cursor(0, None, False )

	@threaded
	def sendPostToEditor(self, widget, path=None, column=None):
		selected_iter = self.tvBlogs.get_selection().get_selected()[1]
		accountName = self.model.get_value(selected_iter, 0)

		if self.isOffline == True:

			newEditor = editor.BloGTKEditor(self)

			self.appbar.push(_('Offline mode enabled, retrieving post from cache'))
			post = self.getOfflinePost()

			if post == False:
				self.appbar.push(_('Could not retrieve post from cache. Aborting.'))

				return False

			else:
				newEditor.getPostFromCache(post)

				return True

		try:
			selected_iter2 = self.tvPosts.get_selection().get_selected()[1]
			postID = self.tvPosts.get_model().get_value(selected_iter2, 0)

			for account in self.accountArray:
				if account['name'] == accountName:
					thisAccount = account

			newEditor = editor.BloGTKEditor(self)

			self.appbar.push(_('Downloading post data'))

			gtk.gdk.threads_enter()
			self.timeout_handler_id = gobject.timeout_add(100, self.update_progress_bar, 'live', 0)   
			gtk.gdk.threads_leave()

			newEditor.getPostForEditing(thisAccount, postID)

			self.timeout_handler_id2 = gobject.timeout_add(100, self.update_progress_bar, 'die', 0)

			self.appbar.push(_('Post sent to editor'))
		
		except TypeError:
			self.appbar.push(_('Please select a post for editing.'))
		except Exception, e:
			self.timeout_handler_id2 = gobject.timeout_add(100, self.update_progress_bar, 'die', 0)
			self.appbar.push(_('An error occurred: %s') % str(e))
			newEditor.destroy(None)

	def getOfflinePost(self):

		selected_iter = self.tvBlogs.get_selection().get_selected()[1]
		accountID = self.model.get_value(selected_iter, 1)
		
		selected_iter2 = self.tvPosts.get_selection().get_selected()[1]
		postTitle = self.tvPosts.get_model().get_value(selected_iter2, 1)
		postId = self.tvPosts.get_model().get_value(selected_iter2, 0)
		postDate = self.tvPosts.get_model().get_value(selected_iter2, 2)

		if os.path.isfile(self.configDir + "/cache/" + base64.b64encode(accountID) + ".xml"):
			f = open(self.configDir + "/cache/" + base64.b64encode(accountID) + ".xml")
			feed = ElementTree.parse(self.configDir + '/cache/' + base64.b64encode(accountID) + '.xml').getroot()

			for entry in feed.findall('entry'):
				
				if entry.find('link').attrib['href'] == postId:
					title = entry.find('title').text
					content = entry.findall('content')[0].text
					try:
						extended = entry.findall('content')[1].text
					except:
						extended = ''
					post_datestamp = time.strptime(entry.find('issued').text, '%Y%m%dT%H:%M:%S')
					postDate = time.strftime('%x %X', post_datestamp)
					tags = []
					cats = []
					if len(entry.findall('category')) != 0:
						for index, tag in enumerate(entry.findall('category')):
							if tag.attrib['scheme'] == 'category':
								cats.append(tag.attrib['term'])
							else:
								tags.append(tag.attrib['term'])

			if len(tags) != 0:
				tag_string = ''
				for index, tag in enumerate(tags):
					if index != (len(tags) - 1):
						tag_string = tag_string + tag + ', '
					else:
						tag_string = tag_string + tag

			if len(cats) != 0:
				cat_string = ''
				for index, cat in enumerate(cats):
					if index != (len(cats) - 1):
						cat_string = cat_string + cat + ', '
					else:
						cat_string = cat_string + cat

			# Create the post object to pass to the editor.
			# Note: Not sure why the whitespace is there, but stripping
			# it out seems to cause no harm.s
			post = {}
			post['title'] = title
			post['content'] = content.lstrip('\n\n\n\t\t\t\t')
			post['extended'] = extended.lstrip('\n\n\n\t\t\t\t')
			post['keywords'] = tag_string
			post['catList'] = cats
			post['categories'] = cat_string
			post['postDate'] = postDate

			return post
		

		else:
			print _('No cache file found.')
			return False



	@threaded
	def createNewPost(self, widget, event=None, data=None):
		selected_iter = self.tvBlogs.get_selection().get_selected()[1]
		accountName = self.model.get_value(selected_iter, 0)

		for account in self.accountArray:
			if account['name'] == accountName:
				thisAccount = account

		self.appbar.push(_('Downloading account data...'))

		gtk.gdk.threads_enter()
		self.timeout_handler_id = gobject.timeout_add(100, self.update_progress_bar, 'live', 0)   
		gtk.gdk.threads_leave()

		newEditor = editor.BloGTKEditor(self)
		newEditor.createNewPost(thisAccount)

		self.timeout_handler_id2 = gobject.timeout_add(100, self.update_progress_bar, 'die', 0)
	
		self.appbar.push('')

	def deletePost(self, widget, data=None):
		selected_iter = self.tvBlogs.get_selection().get_selected()[1]
		accountName = self.model.get_value(selected_iter, 0)

		try:
			selected_iter2 = self.tvPosts.get_selection().get_selected()[1]
			postID = self.tvPosts.get_model().get_value(selected_iter2, 0)
			postName = self.tvPosts.get_model().get_value(selected_iter2, 1)

			for account in self.accountArray:
				if account['name'] == accountName:
					thisAccount = account

			msgtext = _("Are you sure you wish to delete the\n post '%s'?") % postName

			msgbox = gtk.MessageDialog(parent = self.winMain, buttons = gtk.BUTTONS_OK_CANCEL, flags = gtk.DIALOG_MODAL, type = gtk.MESSAGE_WARNING, message_format = msgtext)
			msgbox.set_title(_('Confirm deletion'))
			msgbox.format_secondary_text(_('All information in this post will be deleted and cannot be restored.'))
			result = msgbox.run()
			msgbox.destroy()
			if result == gtk.RESPONSE_OK:
				if thisAccount['api'] == 'mt':
					mt = mtapi.movabletype(thisAccount['endpoint'], thisAccount['username'], thisAccount['password'])
					posts = mt.deletePost(postID)

					self.refreshPosts(None)
			
					self.appbar.push('Deleted post ' + postID)
				if thisAccount['api'] == 'gdata':
					bloggergdata = bloggeratom.BloggerAtom(thisAccount['username'], thisAccount['password'])
					bloggergdata.deletePost(thisAccount['id'], postID)

					self.refreshPosts(None)

				if thisAccount['api'] == 'metaweblog':
					mw = metaweblog.metaWeblog(thisAccount['endpoint'], thisAccount['username'], thisAccount['password'])
					mw.deletePost(postID)

					self.refreshPosts(None)
			else:
				return False

		except TypeError, e:
			self.appbar.push(_('Please select a post to delete.'))
			print str(e)
		except Exception, e:
			self.appbar.push(_('An error occurred: %s') % str(e))

	def goOffline(self, widget, data=None):
		if self.isOffline == False:
			self.appbar.push(_('BloGTK is now offline'))
			self.isOffline = True
			img = gtk.image_new_from_stock(gtk.STOCK_CONNECT, gtk.ICON_SIZE_MENU)
			self.mniOffline.set_image(img)
			self.mniOffline.get_children()[0].set_text(_('Work Online'))
		else:
			self.isOffline = False
			self.appbar.push(_('BloGTK is now back online'))
			img = gtk.image_new_from_stock(gtk.STOCK_DISCONNECT, gtk.ICON_SIZE_MENU)
			self.mniOffline.set_image(img)
			self.mniOffline.get_children()[0].set_text(_('Work Offline'))

	def displayAbout(self, widget, data=None):
		self.dlgAbout.set_transient_for(self.winMain)
		self.dlgAbout.set_position(gtk.WIN_POS_CENTER_ON_PARENT)
		self.dlgAbout.connect('delete_event', self.windowHider)
		self.dlgAbout.connect('destroy', self.windowHider)
		response = self.dlgAbout.run()
		if response == gtk.RESPONSE_CLOSE or response == -6:
			self.windowHider(self.dlgAbout)

	def windowHider(self, widget, event=None, data=None):
		widget.hide()
		return True

	def closeMainWin(self, widget, event=None, data=None):
		if self.changeFlag == False:
			self.winMain.destroy()
			return False
		else:
			msgbox = gtk.MessageDialog(parent = self.winMain, buttons = gtk.BUTTONS_OK_CANCEL, flags = gtk.DIALOG_MODAL, type = gtk.MESSAGE_WARNING, message_format = _('Are you sure you wish to exit BloGTK? Any unsaved entries will be lost.'))
			msgbox.set_title(_('Confirm Exit'))

			result = msgbox.run()

			if result == gtk.RESPONSE_OK:
				msgbox.destroy()
				self.winMain.destroy()
				return False
			else:
				msgbox.destroy()
				return True

	def delete_event(self, widget, event, data=None):
		if self.changeFlag == False:
			return False
		else:
			msgbox = gtk.MessageDialog(parent = self.winMain, buttons = gtk.BUTTONS_OK_CANCEL, flags = gtk.DIALOG_MODAL, type = gtk.MESSAGE_WARNING, message_format = _('Are you sure you wish to exit BloGTK? Any unsaved entries will be lost.'))
			msgbox.set_title(_('Confirm Exit'))

			result = msgbox.run()

			if result == gtk.RESPONSE_OK:
				msgbox.destroy()
				return False
			else:
				msgbox.destroy()
				return True

	def destroy(self, widget, data=None):
		gtk.main_quit()

def main():
 	blogtk = BloGTK()
	blogtk.main()
	gtk.gdk.threads_init()
	gtk.gdk.threads_enter()
	gtk.main()
	gtk.gdk.threads_leave()

if __name__ == '__main__':
 	blogtk = BloGTK()
	blogtk.main()
	gtk.gdk.threads_init()
	gtk.gdk.threads_enter()
	gtk.main()
	gtk.gdk.threads_leave()

