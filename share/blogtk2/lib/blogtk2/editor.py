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

import threading
import time
import os
import base64

import gtk
import gtk.glade
import gnome.ui
import gobject
import gtksourceview2 as gtksourceview
import gtkspell
import pango
import locale
import webkit

import feedparser

import config
import filehandler

import mtapi
import bloggeratom
import metaweblog
import blogger

from blogtk2 import SHARED_FILES

def threaded(f):
    def wrapper(*args):
        t = threading.Thread(target=f, args=args)
        t.start()
    return wrapper

class BloGTKEditor:

	def __init__(self, mainInstance):

		# This gives us control over the main window
		self.mainInstance = mainInstance

		self.glade = gtk.glade.XML(os.path.join(SHARED_FILES, 'glade', 'blogtk2.glade'))

		self.winEditor = self.glade.get_widget('winEditor')
		self.winEditor.connect('delete_event', self.delete_event)	

		self.nbEditorTabs = self.glade.get_widget('nbEditorTabs')

		self.dlgAbout = self.glade.get_widget('dlgAbout')
		
		# Create our fancy new editor system
		# Main Entry Editor
		self.swEditMain = self.glade.get_widget('swEditMain')
		self.sbMain = gtksourceview.Buffer()
		self.scvEditMain = gtksourceview.View(self.sbMain)
		self.swEditMain.add(self.scvEditMain)
		langman = gtksourceview.language_manager_get_default()
		lang = langman.get_language('html')
		self.sbMain.set_language(lang)
		self.sbMain.set_highlight_syntax(True)
		self.scvEditMain.set_wrap_mode(gtk.WRAP_WORD)
		self.sbMain.connect('changed', self.flipChangeFlag)

		# Extended Entry Editor
		self.swEditExtended = self.glade.get_widget('swEditExtended')
		self.sbExtended = gtksourceview.Buffer()
		self.scvEditExtended = gtksourceview.View(self.sbExtended)
		self.swEditExtended.add(self.scvEditExtended)
		self.sbExtended.set_language(lang)
		self.sbExtended.set_highlight_syntax(True)
		self.scvEditExtended.set_wrap_mode(gtk.WRAP_WORD)
		self.sbExtended.connect('changed', self.flipChangeFlag)

		# Set our editor font systems
		self.setEditorFonts()

		# WebKit Post Preview
		self.swEditPreview = self.glade.get_widget('swEditPreview')

		# Get category listing widget
		self.tvCats = self.glade.get_widget('tvCats')

		# Get our other widgets
		self.tePostTitle = self.glade.get_widget('tePostTitle')
		self.teTags = self.glade.get_widget('teTags')
		self.statEdit = self.glade.get_widget('statEdit')
		self.cbComments = self.glade.get_widget('cbComments')
		self.cbTrackbacks = self.glade.get_widget('cbTrackbacks')
		self.cbPublish = self.glade.get_widget('cbPublish')
		self.pbEdit = self.glade.get_widget('pbEdit')

		self.tePostTitle.connect('changed', self.flipChangeFlag)
		self.teTags.connect('changed', self.flipChangeFlag)

		self.tbtnPublish = self.glade.get_widget('tbtnPublish')

		spell = gtkspell.Spell (self.scvEditMain)
		spell.set_language (locale.getlocale()[0])
		self.scvEditMain.show()

		spell2 = gtkspell.Spell (self.scvEditExtended)
		spell2.set_language (locale.getlocale()[0])
		self.scvEditExtended.show()

		self.tsCats = gtk.TreeStore( gobject.TYPE_STRING, gobject.TYPE_BOOLEAN, gobject.TYPE_STRING )
		self.tvCats.set_model(self.tsCats)
		
		# Set up renderers
		self.renderer = gtk.CellRendererToggle()
		self.renderer1 = gtk.CellRendererText()
		self.renderer2 = gtk.CellRendererText()

		self.renderer.connect( 'toggled', self.toggleCat, self.tsCats )
		
		self.column0 = gtk.TreeViewColumn(" ", self.renderer )
		self.column0.set_resizable(True)
		self.column0.add_attribute( self.renderer, "active", 1)
		self.column1 = gtk.TreeViewColumn("Name", self.renderer1, text=0)
		self.column1.set_resizable(True)
		self.column2 = gtk.TreeViewColumn("ID", self.renderer2, text=0)
		self.column2.set_resizable(True)
		self.column2.set_visible(False)

		self.tvCats.append_column( self.column0 )
		self.tvCats.append_column( self.column1 )
		self.tvCats.append_column( self.column2 )

		dic = { 'on_tbtnPublish_clicked' : self.publishPost,
			'on_tbtn_clicked' : self.insertItem,
			'on_tbtnNewFile_clicked' : self.newFile,
			'on_tbtnOpenFile_clicked' : self.openFile,
			'on_tbtnSaveFile_clicked' : self.saveFilePrep,
			'on_tbtnSaveAs_clicked' : self.saveAs,
			'on_editMIQuit_activate' : self.closeWindow,
			'on_tbtnUndo_clicked' : self.undoAction,
			'on_menuitem9_activate' : self.undoAction,
			'on_tbtnRedo_clicked' : self.redoAction,
			'on_tbtnCut_clicked' : self.cutAction,
			'on_tbtnCopyclicked' : self.copyAction,
			'on_tbtnPaste_clicked' : self.pasteAction,
			'on_imagemenuitem16_activate' : self.cutAction,
			'on_imagemenuitem17_activate' : self.copyAction,
			'on_imagemenuitem18_activate' : self.pasteAction,
			'on_menuitem13_activate' : self.editTimeStamp,
			'on_btnSetCurrentTime_clicked' : self.setTimeStampToNow,
			'on_btnSetTimeStamp_clicked' : self.setTimeStamp,
			'on_btnCancelTimeStamp_clicked' : self.closeDlgTimeStamp,
			'on_tbtnInsertLink_clicked' : self.insertLink,
			'on_nbEditorTabs_switch_page' : self.updatePreview,
			'on_tePostTitle_changed' : self.updatePreviewTitle,
			'on_mniEditAbout_activate' : self.displayAbout
		 }
		self.glade.signal_autoconnect(dic)

		# Set our filename flag to blank. When we save our file, we set the
		# filename flag to the location of the saved post.
		self.saveFilename = ''
		self.saveAsFlag = False

		self.changeFlag = False

		# Create our accelerator group
		self.accelGroup = gtk.AccelGroup()
		self.winEditor.add_accel_group(self.accelGroup)
		self.addAccelerators()

	def addAccelerators(self):

		self.setAccelerator(self.glade.get_widget('mniEditNewFile'), 'activate', '<Control>N')
		self.setAccelerator(self.glade.get_widget('mniEditOpenFile'), 'activate', '<Control>O')
		self.setAccelerator(self.glade.get_widget('mniEditSaveFile'), 'activate', '<Control>S')
		self.setAccelerator(self.glade.get_widget('mniEditSaveAsFile'), 'activate', '<Control><Shift>S')
		self.setAccelerator(self.glade.get_widget('mniEditBold'), 'activate', '<Control>B')
		self.setAccelerator(self.glade.get_widget('mniEditItalic'), 'activate', '<Control>I')
		self.setAccelerator(self.glade.get_widget('mniEditPara'), 'activate', '<Control>P')
		self.setAccelerator(self.glade.get_widget('mniEditQuote'), 'activate', '<Control><Alt>B')
		self.setAccelerator(self.glade.get_widget('editMIQuit'), 'activate', '<Control>Q')

	def setAccelerator(self, widget, signal, command):

		key, mod = gtk.accelerator_parse(command)
		widget.add_accelerator(signal, self.accelGroup, key, mod, gtk.ACCEL_VISIBLE)
		return True


	def setEditorFonts(self):
		
		configreader = config.ConfigReader()
		configXML = configreader.getConfigTree()

		settings = configXML.find('settings')
		font = settings.find('editorfont').text
		fontdesc =  pango.FontDescription(font)

		self.scvEditMain.modify_font(fontdesc)
		self.scvEditExtended.modify_font(fontdesc)

	def toggleCat( self, cell, path, model ):

		model[path][1] = not model[path][1]
		return

	def flipChangeFlag(self, widget, data=None):
		self.changeFlag = True
		self.mainInstance.changeFlag = True

	def getPostForEditing(self, account, postID):

		self.winEditor.set_title(self.winEditor.get_title() + ' - ' + account['name'])

		if account['api'] == 'mt':
			self.getPostMT(account, postID)
		if account['api'] == 'gdata':
			self.getPostGData(account, postID)
		if account['api'] == 'metaweblog':
			self.getPostMetaweblog(account, postID)
		if account['api'] == 'blogger':
			self.getPostBlogger(account, postID)

	def getPostGData(self, account, postID):
		
		blogger = bloggeratom.BloggerAtom(account['username'], account['password'])

		feed = blogger.getIndividualPost(account['id'], postID)

		# If title is blank, create an empty title:
		if feed.title.text == None:
			self.tePostTitle.set_text('')
		else:
			self.tePostTitle.set_text(feed.title.text)
		self.sbMain.set_text(feed.content.text)
		# We need to put the GData published date as a normal timestamp. 
		# Instead of processing the RFC 3389 timestamp, we're just going to cut off the unneeded sections.
		self.timestamp = time.strptime(feed.published.text[:19], '%Y-%m-%dT%H:%M:%S')

		# We need to make sure other routines can see our account data
		self.account = account
		self.postID = postID
		
		# For Blogger, we don't need these items
		self.teTags.set_sensitive(False)
		self.tvCats.set_sensitive(False)
		self.cbTrackbacks.set_active(False)
		self.cbTrackbacks.set_sensitive(False)
		self.cbComments.set_active(False)
		self.cbComments.set_sensitive(False)
		self.scvEditExtended.set_sensitive(False)

		self.winEditor.show()

		# Reset our change flags.
		self.changeFlag = False
		self.mainInstance.changeFlag = False

	def getPostMT(self, account, postID):

		mt = mtapi.movabletype(account['endpoint'], account['username'], account['password'])
		cats = mt.getCategoryList(account['id'])

		for cat in cats:
			self.tsCats.append(None, (cat['categoryName'], None, cat['categoryId']))

		post = mt.getPost(postID)

		# Take the post data and fill our editing fields
		self.tePostTitle.set_text(post['title'])

		self.sbMain.set_text(post['description'])
		self.sbExtended.set_text(post['mt_text_more'])
		try:
			self.teTags.set_text(post['mt_keywords'])
		except:
			# If no keywords support, remove the option
			self.teTags.set_sensitive(False)

		try:
			if post['mt_allow_comments'] == 1:
				self.cbComments.set_active(True)
			elif post['mt_allow_comments'] == 0:
				self.cbComments.set_active(False)
		except:
			self.cbComments.set_active(False)
			self.cbComments.set_sensitive(False)

		try:
			if post['mt_allow_pings'] == 1:
				self.cbTrackbacks.set_active(True)
			elif post['mt_allow_pings'] == 0:
				self.cbTrackbacks.set_active(False)
		except:
				self.cbTrackbacks.set_active(False)
				self.cbTrackbacks.set_sensitive(False)

		# Set categories
		self.setPostCats(post['categories'])


		# We need to make sure other routines can see our account data
		self.account = account
		self.postID = postID
		self.timestamp = time.strptime(str(post['dateCreated']), '%Y%m%dT%H:%M:%S')

		self.winEditor.show()
		
		# Reset our change flags.
		self.changeFlag = False
		self.mainInstance.changeFlag = False

	def getPostMetaweblog(self, account, postID):

		mw = metaweblog.metaWeblog(account['endpoint'], account['username'], account['password'])

		post = mw.getPost(postID)

		try:
			cats = mw.getCategoryList(account['id'])

			for cat in cats:
				self.tsCats.append(None, (cat['categoryName'], None, cat['categoryId']))
		except Exception, e:
			print Exception, str(e)

		# Take the post data and fill our editing fields
		self.tePostTitle.set_text(post['title'])

		self.sbMain.set_text(post['description'])
		try:
			self.sbExtended.set_text(post['mt_text_more'])
		except:
			pass
		try:
			self.teTags.set_text(post['mt_keywords'])
		except:
			 # If no keywords support, remove the option
			self.teTags.set_sensitive(False)

		try:
			if post['mt_allow_comments'] == 1:
				self.cbComments.set_active(True)
			elif post['mt_allow_comments'] == 0:
				self.cbComments.set_active(False)
		except:
			self.cbComments.set_active(False)
			self.cbComments.set_sensitive(False)

		try:
			if post['mt_allow_pings'] == 1:
				self.cbTrackbacks.set_active(True)
			elif post['mt_allow_pings'] == 0:
				self.cbTrackbacks.set_active(False)
		except:
				self.cbTrackbacks.set_active(False)
				self.cbTrackbacks.set_sensitive(False)
		
		# Set categories
		self.setPostCats(post['categories'])

		# We need to make sure other routines can see our account data
		self.account = account
		self.postID = postID
		try:
			self.timestamp = time.strptime(str(post['dateCreated']), '%Y%m%dT%H:%M:%S')
		except:
			self.timestamp = time.strptime(str(post['dateCreated']).replace('-', ''), '%Y%m%dT%H:%M:%SZ')

		self.winEditor.show()

		# Reset our change flags.
		self.changeFlag = False
		self.mainInstance.changeFlag = False

	def getPostBlogger(self, account, postID):

		blogger1 = blogger.Blogger(account['endpoint'], account['username'], account['password'])

		post = blogger1.getPost(postID)

		# Turn off widgets not supported by the old Blogger API.
		self.tePostTitle.set_sensitive(False)
		self.teTags.set_sensitive(False)
		self.tvCats.set_sensitive(False)
		self.cbTrackbacks.set_active(False)
		self.cbTrackbacks.set_sensitive(False)
		self.cbComments.set_active(False)
		self.cbComments.set_sensitive(False)
		self.scvEditExtended.set_sensitive(False)
		
		self.sbMain.set_text(post['content'])

		# We need to make sure other routines can see our account data
		self.account = account
		self.postID = postID
		try:
			self.timestamp = time.strptime(str(post['dateCreated']), '%Y%m%dT%H:%M:%S')
		except:
			self.timestamp = time.strptime(str(post['dateCreated']).replace('-', ''), '%Y%m%dT%H:%M:%SZ')

		self.winEditor.show()

		self.changeFlag = False
		self.mainInstance.changeFlag = False


	def getPostFromCache(self, post):
		self.tePostTitle.set_text(post['title'])
		self.sbMain.set_text(post['content'])
		self.sbExtended.set_text(post['extended'])
		self.teTags.set_text(post['keywords'])

		self.winEditor.show()
		self.changeFlag = False
		self.mainInstance.changeFlag = False

	def createNewPost(self, account):

		if account['api'] != 'gdata' and account['api'] != 'blogger':
			conf = config.ConfigReader()
			cats = conf.getCategoryArray(account['name'])

			for cat in cats:
				self.tsCats.append(None, (cat['categoryName'], None, cat['categoryId']))


		elif account['api'] == 'gdata' or account['api'] == 'blogger':
			# For Blogger, we don't need these items
			self.teTags.set_sensitive(False)
			self.tvCats.set_sensitive(False)
			self.cbTrackbacks.set_active(False)
			self.cbTrackbacks.set_sensitive(False)
			self.cbComments.set_active(False)
			self.cbComments.set_sensitive(False)
			self.scvEditExtended.set_sensitive(False)

			if account['api'] == 'blogger':
				self.tePostTitle.set_sensitive(False)

		self.account = account
		self.postID = ''

		self.winEditor.set_title(self.winEditor.get_title() + ' - ' + account['name'])

		self.timestamp = None

		self.winEditor.show()

	def setPostCats(self, cats):
		for cat in cats:
			match_iter = self.search(self.tsCats, self.tsCats.iter_children(None), self.match_func, (0, cat))
			self.tsCats[match_iter][1] = True

	def match_func(self, model, iter, data):
		column, key = data # data is a tuple containing column number, key
		value = model.get_value(iter, column)
		return value == key

	def search(self, model, iter, func, data):
		while iter:
			if func(model, iter, data):
				return iter
			result = self.search(model, model.iter_children(iter), func, data)
			if result: return result
			iter = model.iter_next(iter)
		return None

	def publishPost(self, widget, data=None):

		self.tbtnPublish.set_sensitive(False)

		if self.account['api'] == 'mt':
			self.publishPostMT()
		if self.account['api'] == 'gdata':
			self.publishPostGData()
		if self.account['api'] == 'metaweblog':
			self.publishPostMetaWeblog()
		if self.account['api'] == 'blogger':
			self.publishPostBlogger()

	@threaded
	def publishPostMT(self):

		gtk.gdk.threads_enter()
		self.timeout_handler_id = gobject.timeout_add(100, self.update_progress_bar, 'live', 0)   
		gtk.gdk.threads_leave()

		# Assemble the necessary elements
		title = self.tePostTitle.get_text()
		mainEntry = self.sbMain.get_text(self.sbMain.get_start_iter(), self.sbMain.get_end_iter())
		extendedEntry = self.sbExtended.get_text(self.sbExtended.get_start_iter(), self.sbExtended.get_end_iter())
		keywords = self.teTags.get_text()

		if self.cbComments.get_active() == True:
			comments = 1
		elif self.cbComments.get_active() == False:
			comments = 0

		if self.cbTrackbacks.get_active() == True:
			trackbacks = 1
		elif self.cbTrackbacks.get_active() == False:
			trackbacks = 0		

		# Prepare our list of categories
		self.activeCats = []
		self.tsCats.foreach(self.getActiveCats)

		# We will set the first category as the default
		try:
			self.activeCats[0]['isPrimary'] = True
		except:
			pass

		# Do we want to publish the post? (Default is to publish)
		if self.cbPublish.get_active() == True:
			publish = 0
		else:
			publish = 1

		# Create our post object
		postObject = {}
		postObject['title'] = title
		postObject['description'] = mainEntry
		if self.timestamp != None:
			postObject['dateCreated'] = self.timestamp
		else:
			postObject['dateCreated'] = time.strftime( "%Y%m%dT%H:%M:%SZ", time.gmtime())
		postObject['mt_excerpt'] = ''
		postObject['mt_text_more'] = extendedEntry
		postObject['mt_keywords'] = keywords
		postObject['mt_allow_comments'] = comments
		postObject['mt_allow_pings'] = trackbacks
		postObject['mt_convert_breaks'] = 1
		postObject['publish'] = publish

		mt = mtapi.movabletype(self.account['endpoint'], self.account['username'], self.account['password'])

		# Is this a new post or an edit?

		if self.postID == '':
			try:
				post = mt.createPostWithCats(self.account['id'], postObject, True, self.activeCats)
				# Now any edits will be made as a repost
				self.postID = post
		
				self.timeout_handler_id2 = gobject.timeout_add(100, self.update_progress_bar, 'die', 0)
				self.statEdit.push(1, _('Created new entry with ID %s' % post))
				self.tbtnPublish.set_sensitive(True)

				self.mainInstance.refreshPosts(None)

			except Exception, e:
				print Exception, str(e)
				self.tbtnPublish.set_sensitive(True)
		else:
			try:
				post = mt.repostWithCats(self.account['id'], self.postID, postObject, True, self.activeCats)
				
				self.timeout_handler_id2 = gobject.timeout_add(100, self.update_progress_bar, 'die', 0)
				self.statEdit.push(1, _('Updated entry with ID %s' % post))
				self.tbtnPublish.set_sensitive(True)
	
				self.mainInstance.refreshPosts(None)

			except Exception, e:
				print Exception, str(e)
				self.tbtnPublish.set_sensitive(True)

		self.changeFlag = False
		self.mainInstance.changeFlag = False

	@threaded
	def publishPostMetaWeblog(self):

		gtk.gdk.threads_enter()
		self.timeout_handler_id = gobject.timeout_add(100, self.update_progress_bar, 'live', 0)   
		gtk.gdk.threads_leave()

		# Assemble the necessary elements
		title = self.tePostTitle.get_text()
		mainEntry = self.sbMain.get_text(self.sbMain.get_start_iter(), self.sbMain.get_end_iter())
		extendedEntry = self.sbExtended.get_text(self.sbExtended.get_start_iter(), self.sbExtended.get_end_iter())
		keywords = self.teTags.get_text()

		# Prepare our list of categories
		self.activeCats = []
		self.tsCats.foreach(self.getActiveCats)

		# We will set the first category as the default
		try:
			self.activeCats[0]['isPrimary'] = True
		except:
			print 'No categories selected'

		if self.cbComments.get_active() == True:
			comments = 1
		elif self.cbComments.get_active() == False:
			comments = 0

		if self.cbTrackbacks.get_active() == True:
			trackbacks = 1
		elif self.cbTrackbacks.get_active() == False:
			trackbacks = 0		

		if self.cbPublish.get_active() == True:
			publish = False
		else:
			publish = True

		# Create our post object
		postObject = {}
		postObject['title'] = title
		postObject['description'] = mainEntry
		if self.timestamp:
			postObject['dateCreated'] = self.timestamp
		else:
			postObject['dateCreated'] = time.strftime( "%Y%m%dT%H:%M:%SZ", time.gmtime())
		postObject['mt_excerpt'] = ''
		postObject['mt_text_more'] = extendedEntry
		postObject['mt_keywords'] = keywords
		postObject['mt_allow_comments'] = comments
		postObject['mt_allow_pings'] = trackbacks
		postObject['mt_convert_breaks'] = 1
		postObject['categories'] = self.activeCats

		mw = metaweblog.metaWeblog(self.account['endpoint'], self.account['username'], self.account['password'])

		# Is this a new post or an edit?

		if self.postID == '':
			try:
				post = mw.createPost(self.account['id'], postObject, publish)
				# Now any edits will be made as a repost
				self.postID = post
		
				self.timeout_handler_id2 = gobject.timeout_add(100, self.update_progress_bar, 'die', 0)
				self.statEdit.push(1, _('Created new entry with ID %s' % post))
				self.tbtnPublish.set_sensitive(True)

				self.mainInstance.refreshPosts(None)

			except Exception, e:
				print Exception, str(e)
				self.tbtnPublish.set_sensitive(True)
		else:
			try:
				post = mw.repost(self.account['id'], self.postID, postObject, publish)
				
				self.timeout_handler_id2 = gobject.timeout_add(100, self.update_progress_bar, 'die', 0)
				self.statEdit.push(1, _('Updated entry with ID %s' % post))
				self.tbtnPublish.set_sensitive(True)
	
				self.mainInstance.refreshPosts(None)

			except Exception, e:
				print Exception, str(e)
				self.tbtnPublish.set_sensitive(True)

		self.changeFlag = False
		self.mainInstance.changeFlag = False

	@threaded
	def publishPostGData(self):

		gtk.gdk.threads_enter()
		self.timeout_handler_id = gobject.timeout_add(100, self.update_progress_bar, 'live', 0)   
		gtk.gdk.threads_leave()

		blogger = bloggeratom.BloggerAtom(self.account['username'], self.account['password'])

		# Assemble our post elements
		title = self.tePostTitle.get_text()
		mainEntry = self.sbMain.get_text(self.sbMain.get_start_iter(), self.sbMain.get_end_iter())

		# Is this a draft or not?
		is_draft = self.cbPublish.get_active()

		# Is there a timestamp?
		if self.timestamp:
			offset = self.getTZOffset()
			timestamp = time.strftime('%Y-%m-%dT%H:%M:%S.001' + offset + ':00', self.timestamp)
		else:
			timestamp = None

		# Post or repost? Deal or no deal?
		if self.postID == '':

			try:
				post = blogger.createPost(self.account['id'], title, mainEntry, self.account['username'], is_draft, timestamp)

				self.timeout_handler_id2 = gobject.timeout_add(100, self.update_progress_bar, 'die', 0)
				self.statEdit.push(1, _('Created new entry with ID %s' % post.id.text.split("-")[-1]))
			
				# Make sure we have our repost flag set
				self.postID = post.id.text.split("-")[-1]

				self.mainInstance.refreshPosts(None)

			except Exception, e:
					print Exception, str(e)

		else:
			try:
				post = blogger.editPost(self.account['id'], self.postID, title, mainEntry, self.account['username'], is_draft, timestamp)
	
				self.timeout_handler_id2 = gobject.timeout_add(100, self.update_progress_bar, 'die', 0)
				self.statEdit.push(1, _('Edited post ID %s' % post.id.text.split("-")[-1]))
				self.tbtnPublish.set_sensitive(True)

				self.mainInstance.refreshPosts(None)

			except Exception, e:
				print Exception, str(e)
				self.tbtnPublish.set_sensitive(True)

		self.changeFlag = False
		self.mainInstance.changeFlag = False

	@threaded
	def publishPostBlogger(self):

		gtk.gdk.threads_enter()
		self.timeout_handler_id = gobject.timeout_add(100, self.update_progress_bar, 'live', 0)   
		gtk.gdk.threads_leave()

		# Assemble the necessary elements
		mainEntry = self.sbMain.get_text(self.sbMain.get_start_iter(), self.sbMain.get_end_iter())

		if self.cbPublish.get_active() == True:
			publish = False
		else:
			publish = True

		# Create our post object
		postObject = {}
		postObject['content'] = mainEntry
		if self.timestamp:
			postObject['dateCreated'] = self.timestamp
		else:
			postObject['dateCreated'] = time.strftime( "%Y%m%dT%H:%M:%SZ", time.gmtime())

		blogger1 = blogger.Blogger(self.account['endpoint'], self.account['username'], self.account['password'])

		# Is this a new post or an edit?

		if self.postID == '':
			try:
				post = blogger1.createPost(self.account['id'], postObject, publish)
				# Now any edits will be made as a repost
				self.postID = post
		
				self.timeout_handler_id2 = gobject.timeout_add(100, self.update_progress_bar, 'die', 0)
				self.statEdit.push(1, _('Created new entry with ID %s' % post))
				self.tbtnPublish.set_sensitive(True)

				self.mainInstance.refreshPosts(None)

			except Exception, e:
				print Exception, str(e)
				self.tbtnPublish.set_sensitive(True)
		else:
			try:
				post = blogger1.repost(self.account['id'], self.postID, postObject, publish)
				
				self.timeout_handler_id2 = gobject.timeout_add(100, self.update_progress_bar, 'die', 0)
				self.statEdit.push(1, _('Updated entry with ID %s' % post))
				self.tbtnPublish.set_sensitive(True)
	
				self.mainInstance.refreshPosts(None)

			except Exception, e:
				print Exception, str(e)
				self.tbtnPublish.set_sensitive(True)

		self.changeFlag = False
		self.mainInstance.changeFlag = False


		
	def getActiveCats(self, model, path, iter):
		if model.get_value(iter, 1) == True:
			catStruct = {}
			# http://www.sixapart.com/developers/xmlrpc/movable_type_api/mtsetpostcategories.html
			# categoryID should be a integer
			catStruct['categoryId'] = int(model.get_value(iter, 2))
			catStruct['isPrimary'] = False
			self.activeCats.append(catStruct)

	def editTimeStamp(self, widget, data=None):

		self.dlgTime = self.glade.get_widget('dlgTime')

		self.dlgTime.connect("destroy", self.hideDialog)
		self.dlgTime.connect("delete_event", self.hideDialog)


		self.lblCurrentTime = self.glade.get_widget('lblCurrentTime')
		self.calPostDate = self.glade.get_widget('calPostDate')

		self.spinHour = self.glade.get_widget('spinHour')
		self.spinMinute = self.glade.get_widget('spinMinute')
		self.spinSecond = self.glade.get_widget('spinSecond')

		self.btnCancelTimeStamp = self.glade.get_widget('btnCancelTimeStamp')

		# If our timestamp field has not been set, make it now
		if self.timestamp == None:
			theTime = time.localtime()
		else:
			theTime = self.timestamp

		# Set our calendar
		self.calPostDate.select_month(int(time.strftime("%m", theTime)) - 1, int(time.strftime("%Y", theTime)))
		self.calPostDate.select_day(int(time.strftime('%d', theTime)))

		# Set our time spinners
		self.spinHour.set_value(int(time.strftime("%H", theTime)))
		self.spinMinute.set_value(int(time.strftime("%M", theTime)))
		self.spinSecond.set_value(int(time.strftime("%S", theTime)))	

		self.lblCurrentTime.set_text(_('Current Time: ') + time.strftime("%H:%M:%S", time.localtime()))

		self.dlgTime.show()

	def setTimeStamp(self, widget, data=None):
		
		date = self.calPostDate.get_date()
		# When we get our values, we need to zero-pad them to form a proper timestamp
		year = date[0]
		month = '%02d' % (date[1] + 1) # Correct for January being month zero - which seems kinda silly
		day = '%02d' % (date[2])

		hour = '%02d' % (int(self.spinHour.get_value()))
		minute = '%02d' % (int(self.spinMinute.get_value()))
		second = '%02d' % (int(self.spinSecond.get_value()))

		offset = self.getTZOffset()

		dateString = str(year) + str(month) + str(day) + 'T' + str(hour) + ':' + str(minute) + ':' + str(second) + offset + ':00'

		self.timestamp = time.gmtime(time.mktime(time.strptime(dateString, '%Y%m%dT%H:%M:%S' + offset + ':00')))

		self.hideDialog(self.dlgTime)

	def setTimeStampToNow(self, widget, data=None):

		theTime = time.localtime()

		# Set our calendar
		self.calPostDate.select_month(int(time.strftime("%m", theTime)) - 1, int(time.strftime("%Y", theTime)))
		self.calPostDate.select_day(int(time.strftime('%d', theTime)))

		# Set our time spinners
		self.spinHour.set_value(int(time.strftime("%H", theTime)))
		self.spinMinute.set_value(int(time.strftime("%M", theTime)))
		self.spinSecond.set_value(int(time.strftime("%S", theTime)))

	def closeDlgTimeStamp(self, widget, data=None):

		self.hideDialog(self.dlgTime)

	def getTZOffset(self):
		offset = time.timezone / 60 / 60
		if offset > 0 and offset < 10:
			offset = '+0' + str(offset)
		if offset > 0 and offset >= 10:
			offset = '+' + str(offset)
		if offset < 0 and offset > -10:
			offset = '-0' + str(offset)
		if offset < 0 and offset <= -10:
			offset = '-' + str(offset)
		else:
			offset = '-00'

		return offset
			
	def insertItem(self, widget, data=None):
		name = gtk.glade.get_widget_name(widget)
		
		if name == 'tbtnBold' or name == 'mniEditBold':
			tagStart = '<strong>'
			tagEnd = '</strong>'
		if name == 'tbtnItalic' or name == 'mniEditItalic':
			tagStart = '<em>'
			tagEnd = '</em>'
		if name == 'tbtnPara' or name == 'mniEditPara':
			tagStart = '<p>'
			tagEnd = '</p>'
		if name == 'tbtnQuote' or name == 'mniEditQuote':
			tagStart = '<blockquote>'
			tagEnd = '</blockquote>'
		if name == 'tbtnAlignLeft' or name == 'mniEditAlignLeft':
			tagStart = '<div style="text-align: left;">'
			tagEnd = '</div>'
		if name == 'tbtnAlignCenter' or name == 'mniEditAlignCenter':
			tagStart = '<div style="text-align: center;">'
			tagEnd = '</div>'
		if name == 'tbtnAlignRight' or name == 'mniEditAlignRight':
			tagStart = '<div style="text-align: right;">'
			tagEnd = '</div>'
		if name == 'tbtnNumList' or name == 'mniEditNumList':
			tagStart = '<ol><li>'
			tagEnd = '</li></ol>'
		if name == 'tbtnList' or name == 'mniEditList':
			tagStart = '<ul><li>'
			tagEnd = '</li></ul>'
		else:
			pass

		focused = self.winEditor.get_focus()

		try:
			self.buffer = focused.get_buffer()

			selMark = self.buffer.get_selection_bound()
			insMark = self.buffer.get_insert()

			try:
				start, end = self.buffer.get_selection_bounds()
				text = self.buffer.get_text(start, end)
				new_text = tagStart + text + tagEnd
				self.buffer.begin_user_action()
				self.buffer.delete(start, end)
				self.buffer.end_user_action()
				self.buffer.insert(start, new_text, -1)
				cur_pos = self.buffer.get_iter_at_mark(self.buffer.get_insert())
				match_start, match_end = cur_pos.backward_search(text, gtk.TEXT_SEARCH_TEXT_ONLY)
				self.buffer.move_mark(selMark, match_end)
				self.buffer.move_mark(insMark, match_start)
			except:
				self.buffer.begin_user_action()
				self.buffer.insert_at_cursor(tagStart + tagEnd, -1)
				end = self.buffer.get_iter_at_mark(selMark)
				end.backward_chars(len(tagEnd))
				self.buffer.place_cursor(end)
				self.buffer.end_user_action()
		except:
			pass

	def insertLink(self, widget, data=None):
		
		newLinkInserter = LinkManager(self.glade, self.winEditor)
		newLinkInserter.insertLink()

		del newLinkInserter

	def updatePreviewTitle(self, widget, data=None):

		# This breaks in Karmic, for reasons not yet known.
		# So for now we'll delete this.
		#self.updatePreview(self.nbEditorTabs, None, None)
		pass

	def updatePreview(self, widget, event, data=None):

		# 2.0.1 - If there's a widget inside the preview scrolled
		# window, let's delete it.

		if self.swEditPreview.get_children():
			self.swEditPreview.remove(self.swEditPreview.get_children()[0])

		wkPreview = webkit.WebView()
		self.swEditPreview.add(wkPreview)
		wkPreview.show()

		postTitle = self.tePostTitle.get_text()
		mainEntry = self.sbMain.get_text(self.sbMain.get_start_iter(), self.sbMain.get_end_iter())
		extendedEntry = self.sbExtended.get_text(self.sbExtended.get_start_iter(), self.sbExtended.get_end_iter())
	
		previewString = _('<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">\
			<html xmlns="http://www.w3.org/1999/xhtml">\
			<head>\
			<title>' + postTitle + '</title>\
			</head>\
			<body>\
			<div style="border-bottom: 1px solid #000;"><h2 style="padding: 0; margin: 0;">' + postTitle + '</h2><br />\
			</div>\
			' + mainEntry + '\
			<div>' + extendedEntry + '</div>''\
			</body>\
			</html>')

		wkPreview.load_html_string(previewString, 'file:///')

	def openFile(self, widget, data=None):
		handler = filehandler.FileHandler()

		result = handler.openFile(self.winEditor)

		if result[0] == True:
			self.saveFilename = result[1]

			# Check if fields active first?
			self.tePostTitle.set_text(result[2][0])
			self.sbMain.set_text(result[2][1])
			self.sbExtended.set_text(result[2][2])
			self.teTags.set_text(result[2][3])

			self.changeFlag = False
			self.mainInstance.changeFlag = False

		if result[0] == False and result[1] == 'cancel':
			self.statEdit.push(1, _('Open Canceled'))
		if result[0] == False and result[1] != 'cancel':
			msgbox = gtk.MessageDialog(parent = self.winEditor, buttons = gtk.BUTTONS_CLOSE, flags = gtk.DIALOG_MODAL, type = gtk.MESSAGE_WARNING, message_format = _('An error occurred opening your file: %s ' % result[1]))
			msgbox.set_title(_('Error Opening File'))
			result = msgbox.run()
			msgbox.destroy()
			self.statEdit.push(1, _('File Open Failed: %s' % result[1]))

			return True

	def newFile(self, widget, data=None):

			msgbox = gtk.MessageDialog(parent = self.winEditor, buttons = gtk.BUTTONS_OK_CANCEL, flags = gtk.DIALOG_MODAL, type = gtk.MESSAGE_WARNING, message_format = _('Are you sure you wish to create a new post? Any unsaved text will be lost.'))
			msgbox.set_title(_('Create New Post'))

			result = msgbox.run()

			if result == gtk.RESPONSE_OK:
				self.postid = ''
				self.tePostTitle.set_text('')
				self.sbExtended.set_text('')
				self.sbMain.set_text('')
				self.teTags.set_text('')
				# Clear any active categories.
				self.tsCats.foreach(self.clearCats)
				self.changeFlag = False
				self.mainInstance.changeFlag = False
				msgbox.destroy()
			else:
				msgbox.destroy()

	def clearCats(self, model, path, iter):
		if model.get_value(iter, 1) == True:
			self.tsCats[iter][1] = False

	def saveFilePrep(self, widget, data=None):

		handler = filehandler.FileHandler()

		# We need to start assembling our post struct. BloGTK will save the post title, the post entry
		# the extended entry, and any keywords. Categories and other settings are not saved to make
		# it easier to move posts between different blogs
		postStruct = []
		postStruct.append(self.tePostTitle.get_text())
		postStruct.append(self.sbMain.get_text(self.sbMain.get_start_iter(), self.sbMain.get_end_iter()))
		postStruct.append(self.sbExtended.get_text(self.sbExtended.get_start_iter(), self.sbExtended.get_end_iter()))
		postStruct.append(self.teTags.get_text())

		if self.saveFilename == '' or self.saveAsFlag == True:

			result = handler.saveFile(postStruct, self.winEditor)

			if result[0] == True:
				self.statEdit.push(1, _('File Saved As: %s' % result[1]))
				self.saveFilename = result[1]
				# Reset our saveAs flag
				if self.saveAsFlag == True:
					self.saveAsFlag = False
				self.changeFlag = False
				self.mainInstance.changeFlag = False

			if result[0] == False and result[1] == 'cancel':
				self.statEdit.push(1, _('Save Canceled'))
			if result[0] == False and result[1] != 'cancel':
				msgbox = gtk.MessageDialog(parent = self.winEditor, buttons = gtk.BUTTONS_CLOSE, flags = gtk.DIALOG_MODAL, type = gtk.MESSAGE_WARNING, message_format = _('An error occurred saving your file: %s') % result[1])
				msgbox.set_title(_('Error Saving File'))
				result = msgbox.run()
				msgbox.destroy()
				self.statEdit.push(1, _('Save Failed'))

			return True


		# If we've already saved a file, we don't need to bring up our dialog.
		if self.saveFilename != '':

			result = handler.resaveFile(postStruct, self.saveFilename)

			if result[0] == True:
				self.statEdit.push(1, _('File Saved.'))
				self.changeFlag = False
				self.mainInstance.changeFlag = False
			if result[0] == False:
				msgbox = gtk.MessageDialog(parent = self.winEditor, buttons = gtk.BUTTONS_CLOSE, flags = gtk.DIALOG_MODAL, type = gtk.MESSAGE_WARNING, message_format = _('An error occurred saving your file: %s' % result[1]))
				msgbox.set_title(_('Error Saving File'))
				result = msgbox.run()
				msgbox.destroy()
				self.statEdit.push(1, _('Save Failed'))

	def saveAs(self, widget, data=None):

		# If the user wants to save as a new file, we want to bring up the
		# save dialog again.
		self.saveAsFlag = True

		self.saveFilePrep(None)


	def cutAction(self, widget, data=None):
		focused = self.winEditor.get_focus()

		focused.emit("cut-clipboard")
		
		return True

	def copyAction(self, widget, data=None):
		focused = self.winEditor.get_focus()

		focused.emit("copy-clipboard")

		return True

	def pasteAction(self, widget, data=None):
		focused = self.winEditor.get_focus()

		focused.emit("paste-clipboard")

		return True

	def undoAction(self, widget, data=None):
		focused = self.winEditor.get_focus()

		try:
			if focused.get_buffer().can_undo():
				focused.get_buffer().undo()
		except:
			pass

	def redoAction(self, widget, data=None):
		focused = self.winEditor.get_focus()

		try:
			if focused.get_buffer().can_redo():
				focused.get_buffer().redo()
		except:
			pass

	def update_progress_bar(self, mortality, foo):

 		if mortality == 'live':
			self.pbEdit.pulse()
			return True
		if mortality == 'die':
			gobject.source_remove(self.timeout_handler_id)
			self.pbEdit.set_fraction(0.0)
			return False

	def displayAbout(self, widget, data=None):
		self.dlgAbout.set_transient_for(self.winEditor)
		self.dlgAbout.set_position(gtk.WIN_POS_CENTER_ON_PARENT)
		self.dlgAbout.connect('delete_event', self.hideDialog)
		self.dlgAbout.connect('destroy', self.hideDialog)
		self.dlgAbout.set_name(_('BloGTK Editor'))
		response = self.dlgAbout.run()
		if response == gtk.RESPONSE_CLOSE or response == -6:
			self.hideDialog(self.dlgAbout)

	def hideDialog(self, widget, data=None):
		widget.hide()
		return True

	def closeWindow(self, widget, data=None):
		if self.changeFlag == False:
			self.winEditor.destroy()
			return False
		else:
			msgbox = gtk.MessageDialog(parent = self.winEditor, buttons = gtk.BUTTONS_OK_CANCEL, flags = gtk.DIALOG_MODAL, type = gtk.MESSAGE_WARNING, message_format = _('Are you sure you wish to exit the editor? Any unsaved text will be lost.'))
			msgbox.set_title(_('Confirm Close'))

			result = msgbox.run()

			if result == gtk.RESPONSE_OK:
				msgbox.destroy()
				# Reset the change flag in the main instance.
				self.mainInstance.changeFlag = False
				self.winEditor.destroy()
				return False
			else:
				msgbox.destroy()
				return True	

	def delete_event(self, widget, event, data=None):
		if self.changeFlag == False:
			self.winEditor.destroy()
			return False
		else:
			msgbox = gtk.MessageDialog(parent = self.winEditor, buttons = gtk.BUTTONS_OK_CANCEL, flags = gtk.DIALOG_MODAL, type = gtk.MESSAGE_WARNING, message_format = _('Are you sure you wish to exit the editor? Any unsaved text will be lost.'))
			msgbox.set_title(_('Confirm Close'))

			result = msgbox.run()

			if result == gtk.RESPONSE_OK:
				msgbox.destroy()
				# Reset the change flag in the main instance.
				self.mainInstance.changeFlag = False
				return False
			else:
				msgbox.destroy()
				return True	

	def destroy(self, widget, data=None):
		return False

class LinkManager:

	def __init__(self, glade, editor):

		self.glade = gtk.glade.XML(os.path.join(SHARED_FILES, 'glade', 'blogtk2.glade'))

		self.winEditor = editor
		# Get widgets
		
		self.dlgInsertLink = self.glade.get_widget('dlgInsertLink')
		self.teLinkURI = self.glade.get_widget('teLinkURI')
		self.teLinkText = self.glade.get_widget('teLinkText')
		self.teLinkTitle = self.glade.get_widget('teLinkTitle')
		self.btnInsertLink = self.glade.get_widget('btnInsertLink')
		self.btnCancelLinkInsert = self.glade.get_widget('btnCancelLinkInsert')

		self.btnCancelLinkInsert.connect('clicked', self.destroyDialog)

		self.btnInsertLink.connect('clicked', self.doLinkInsertion)

		self.dlgInsertLink.set_transient_for(self.winEditor)

		self.dlgInsertLink.show()

	def insertLink(self):

		# Is there anything selected? If so, we autofill our link text with that.
		focused = self.winEditor.get_focus()
		
		# Clear our fields.
		self.teLinkText.set_text('')
		self.teLinkTitle.set_text('')
		self.teLinkURI.set_text('')

		try:
			self.buffer = focused.get_buffer()

			start, end = self.buffer.get_selection_bounds()
			text = self.buffer.get_text(start, end)

			self.teLinkText.set_text(text)

		except:
			pass

		# Is there something link like in the clipboard? If so, then we autofill the URI field with that.
		clipboard = gtk.Clipboard()

		text = clipboard.wait_for_text()

		try:
			if (text.startswith("http://") or text.startswith("https://")):
				self.teLinkURI.set_text(text)
		except:
			pass

	def doLinkInsertion(self, widget, data=None):

		linkURI = self.teLinkURI.get_text()
		linkText = self.teLinkText.get_text()
		linkTitle = self.teLinkTitle.get_text()

		# We're going to replace our selected text with the link on the off chance
		#that the user changes the link text in the dialog.

		if linkTitle != '':
			link = '<a href="' + linkURI + '" title="' + linkTitle + '">' + linkText + '</a>'
		else:
			link = '<a href="' + linkURI + '">' + linkText + '</a>'

		# Is there a selection? If so, delete it...
		focused = self.winEditor.get_focus()

		try:
			try:
				self.buffer = focused.get_buffer()

				start, end = self.buffer.get_selection_bounds()

				self.buffer.begin_user_action()
				text = self.buffer.delete(start, end)
				self.buffer.insert(start, link)
				self.buffer.end_user_action()

				self.dlgInsertLink.destroy()
			
			except:
				self.buffer.begin_user_action()
				self.buffer.insert_at_cursor(link)
				self.buffer.end_user_action()

				self.dlgInsertLink.destroy()
		except:
			pass

		return True

	def hideDialog(self, widget, data=None):
		widget.hide()
		return True

	def destroyDialog(self, widget, data=None):
		self.dlgInsertLink.destroy()
		return True


