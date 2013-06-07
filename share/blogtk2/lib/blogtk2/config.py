#!/usr/bin/env python

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

import xml.dom.minidom

# This library in great for pulling data from even badly-formed
# markup
from BeautifulSoup import BeautifulSoup

import gtk
import gtk.glade
import gobject
import pango

import base64
import urllib2
import threading

import os

from blogtk2 import SHARED_FILES

# This dictionary matches the systems with each blogging API they use.
systems = {
	'WordPress' : 'mt',
	'Movable Type' : 'mt',
	'Melody' : 'mt',
	'TextPattern' : 'mt',
	'Windows Live Spaces' : 'metaweblog',
	'Blogger' : 'gdata',
	'MetaWeblog' : 'metaweblog',
	'b2evolution' : 'metaweblog',
	'Habari'	:	'metaweblog',
	'LifeType' : 'metaweblog',
	'Drupal'	:	'metaweblog',
	'Expression Engine' : 'metaweblog',
	'Blogger 1.0' : 'blogger'
}

def threaded(f):
    def wrapper(*args):
        t = threading.Thread(target=f, args=args)
        t.start()
    return wrapper


class ConfigReader:

	def __init__(self):
		self.configDir = os.path.expanduser('~') + '/.BloGTK'
		self.configFile = self.configDir + '/config.xml'
		self.tree = ElementTree.parse(self.configFile).getroot()

	def getConfigTree(self):

		return self.tree

	def getConfigArray(self):

		accountData = []

		blogs = self.tree.findall('blog')
		for blog in blogs:
			account = { 
				'name' : blog.attrib['name'],
				'id' : blog.attrib['id'],
				'uri' : blog.find('uri').text,
				'endpoint' : blog.find('endpoint').text,
				'api' : blog.find('api').text,
				'system' : blog.find('system').text,
				'username' : blog.find('username').text,
				'password' : base64.b64decode(blog.find('password').text),
				'pullcount' : int(blog.find('pullcount').text)
			}
			accountData.append(account)

		return accountData
		
	def getCategoryArray(self, blogname):

		# ElementTree can't handle a simple XPath query like blog[@name = "somename"] -- lame.
		
		blogs = self.tree.findall('blog')

		catArray = []

		for blog in blogs:
			if blog.attrib['name'] == blogname:
				cats = blog.findall('categories/category')
				# This is like herding cats
				for cat in cats:
					category = {
						'categoryId' : cat.attrib['id'],
						'categoryName' : cat.attrib['name']
					}
					catArray.append(category)

		return catArray

class ConfigWriter:

	def __init__(self):
		self.configFile = os.path.expanduser('~') + '/.BloGTK' + '/config.xml'
		self.tree = ElementTree.parse(self.configFile).getroot()

	def writeCategoryArray(self, blogname, catsArray):

		# We need to refresh our config file object each time we do a write.
		# TODO: Better config file handling.
		self.configFile = os.path.expanduser('~') + '/.BloGTK' + '/config.xml'
		self.tree = ElementTree.parse(self.configFile).getroot()
		
		blogs = self.tree.findall('blog')
		for blog in blogs:
			if blog.attrib['name'] == blogname:
				cats = blog.find('categories')
				if cats:
					blog.remove(cats)
				newCat = ElementTree.Element('categories')
				blog.append(newCat)
				for cat in catsArray:
					try:
						newCat.append(ElementTree.Element('category', name=cat['categoryName'], id=cat['categoryId']))
					except:
						# This is due to Windows Live Spaces not handling categories in
						# a rational manner. Quelle surprise.
						newCat.append(ElementTree.Element('category', name=cat['title'], id=cat['title']))

				ElementTree.ElementTree(self.tree).write(self.configFile)

				# For security, we want our config file set chmod 0600 so others can't read the file.
				os.chmod(self.configFile, 0600)

class ConfigGUI:

	def __init__(self, mainInstance):

		self.mainInstance = mainInstance

		self.glade = gtk.glade.XML(os.path.join(SHARED_FILES, 'glade', 'blogtk2.glade'))

		self.dlgAccounts = self.glade.get_widget('dlgAccounts')
		self.dlgAccounts.connect('delete_event', self.closeWindow)

		# Grab our widgets... which sounds faintly dirty...
		self.tvAccountList = self.glade.get_widget('tvAccountList')
		self.teAcctName = self.glade.get_widget('teAcctName')
		self.teAcctAddress = self.glade.get_widget('teAcctAddress')
		self.teAcctEndpoint = self.glade.get_widget('teAcctEndpoint')
		self.teAcctUser = self.glade.get_widget('teAcctUser')
		self.teAcctPass = self.glade.get_widget('teAcctPass')
		self.teAcctBlogID = self.glade.get_widget('teAcctBlogID')
		self.cmbAcctSystem = self.glade.get_widget('cmbAcctSystem')
		self.spinPullcount = self.glade.get_widget('spinPullcount')
		self.tvFontPreview = self.glade.get_widget('tvFontPreview')

		#Set up our TreeView
		self.tsAccts = gtk.TreeStore( gobject.TYPE_STRING )
		self.tvAccountList.set_model(self.tsAccts)
		self.column0 = gtk.TreeViewColumn("Account Name", gtk.CellRendererText(), text=0 )
		self.tvAccountList.append_column(self.column0)

		# Grab our initial config
		self.accountTree = ConfigReader().getConfigTree()

		# Initiate Blog System Listing
		self.initSysList()
	
		# Populate our accounts
		self.populateAccountList()

		# Set the font preview for our editor font
		self.setFontPreview()

		# Initialize our change flag. If there is a change to any data, we need to set this to true
		self.changeFlag = False

		# This prevents multiple name error problems.
		self.nameErrorFlag = False

		# This array will hold our deleted blogs. On exit, should any blogs be deleted, we need to
		# delete their cache file as well.
		self.deletedBlogArray = []

		self.dlgAccounts.show()

		dic = { 
			'on_tvAccountList_cursor_changed' : self.changeAcct,
			'on_btnAcctIntrospection_clicked' : self.doIntrospection,
			'on_btnAcctAdd_clicked' : self.addAccount,
			'on_btnAccountRemove_clicked' : self.removeAccount,
			'on_teAcctName_focus_out_event' : self.updateData,
			'on_teAcctAddress_focus_out_event' : self.updateData,
			'on_teAcctEndpoint_focus_out_event' : self.updateData,
			'on_teAcctUser_focus_out_event' : self.updateData,
			'on_teAcctPass_focus_out_event' : self.updateData,
			'on_teAcctBlogID_focus_out_event' : self.updateData,
			'on_cmbAcctSystem_changed' : self.updateData,
			'on_spinPullcount_focus_out_event' : self.updateData,
			'on_widgetChanged_event' : self.switchChangeFlag,
			'on_btnAccountAccept_clicked' : self.saveAccount,
			'on_btnEditorFont_clicked' : self.setEditorFont,
			'on_btnAccountCancel_clicked' : self.closeWindow
		}
		self.glade.signal_autoconnect(dic)

	def initSysList(self):

		self.liststore = gtk.ListStore(str, str, 'gboolean')

		self.cmbAcctSystem.set_model(self.liststore)

		self.tvcolumn = gtk.TreeViewColumn()

		for item in sorted(systems.keys()):
			self.liststore.append([0, item, True])

		self.cellpb = gtk.CellRendererPixbuf()
		self.cell = gtk.CellRendererText()

		self.cmbAcctSystem.pack_start(self.cellpb, False)
		self.cmbAcctSystem.pack_start(self.cell, True)


		#self.cmbAcctSystem.set_cell_data_func(self.cellpb, self.make_pb)
		self.cmbAcctSystem.set_attributes(self.cell, text=1)

	def populateAccountList(self, index=None):

		self.tsAccts.clear()

		blogs = self.accountTree.findall('blog')

		for blog in blogs:
			self.tsAccts.append(None, [blog.attrib['name']])

		if not index == None:
			self.tvAccountList.get_selection().select_path(index)	
			self.tvAccountList.set_cursor(index, None, False )

		if index == None:
			# Because predestination is cool...
			sel = self.tvAccountList.get_selection()
			sel.set_mode(gtk.SELECTION_SINGLE)

			sel.select_path(0)
			self.tvAccountList.set_cursor(0, None, False )

			self.changeAcct(None)

	def changeAcct(self, widget, data=None):
		
		selected_iter = self.tvAccountList.get_selection().get_selected()[1]
		acctName = self.tsAccts.get_value(selected_iter, 0)

		blogs = self.accountTree.findall('blog')

		for blog in blogs:
			if blog.attrib['name'] == acctName:
				self.teAcctName.set_text(blog.attrib['name'])
				self.teAcctAddress.set_text(blog.find('uri').text)
				self.teAcctEndpoint.set_text(blog.find('endpoint').text)
				self.teAcctUser.set_text(blog.find('username').text)
				self.teAcctPass.set_text(base64.b64decode(blog.find('password').text))
				self.teAcctBlogID.set_text(blog.attrib['id'])
				if blog.find('system').text == 'Blogger':
					self.spinPullcount.set_value(25)
					self.spinPullcount.set_sensitive(False)
				else:
					self.spinPullcount.set_sensitive(True)
					self.spinPullcount.set_value(float(blog.find('pullcount').text))

				self.activeBlog = blog

		match_iter = self.search(self.liststore, self.liststore.iter_children(None), self.match_func, (1, self.activeBlog.find('system').text))
		self.cmbAcctSystem.set_active_iter(match_iter)


	# ADD ACCOUNT FUNCTIONS
	# ==================================================

	def addAccount(self, widget, data=None):
			
		# We don't want to add a new account until the last one has
		# been given a new name

		blogs = self.accountTree.findall('blog')

		for blog in blogs:
			if blog.attrib['name'] == 'New Account':
				return False
		
		e = ElementTree.Element

		# When we add, change, or remove any of our blog settings, we're doing so to an
		# in-memory copy of the actual config XML tree. This makes things immensely
		# simpler.
		newAccount = e('blog', name='New Account', id='')
		endpoint = e('endpoint')
		endpoint.text = ''		
		newAccount.append(endpoint)
		uri = e('uri')
		uri.text = ''		
		newAccount.append(uri)
		username = e('username')
		username.text = ''		
		newAccount.append(username)
		password = e('password')
		password.text = ''		
		newAccount.append(password)
		api = e('api')
		api.text = ''		
		newAccount.append(api)
		system = e('system')
		system.text = 'Blogger'		
		newAccount.append(system)
		pullcount = e('pullcount')
		pullcount.text = '20'
		newAccount.append(pullcount)

		self.accountTree.append(newAccount)

		self.activeBlog = newAccount

		# We want to select the newly-created account.
		self.populateAccountList(len(self.accountTree) - 2)

		# Set our change flag to true
		self.changeFlag = True

		# Here the focus gets set to the account name field.
		self.teAcctName.grab_focus()

	def updateData(self, widget, data=None):

		if self.liststore.get_value(self.cmbAcctSystem.get_active_iter(), 1) == 'Blogger':
			self.spinPullcount.set_sensitive(False)
		else:
			self.spinPullcount.set_sensitive(True)

		if widget.name == 'teAcctName':
			x = self.teAcctName.get_text()
			acctName = unicode(x, 'utf-8')

			# We need to get the selection, since we don't want to compare
			# names with the currently selected item.
			selected_iter = self.tvAccountList.get_cursor()[0][0]

			names = []

			for index, row in enumerate(self.tsAccts):
				if index == selected_iter:
					pass
				else:
					if acctName == row[0]:
						if self.nameErrorFlag == False:
							dialog = self.dialogCreator('Accounts must have unique names')
							self.teAcctName.grab_focus()
							dialog.destroy()
						
							self.nameErrorFlag = True

						self.teAcctName.grab_focus()

						return False

			self.activeBlog.attrib['name'] = acctName

			self.populateAccountList(selected_iter)
		
		if widget.name == 'teAcctAddress':
			url = widget.get_text()
			if not (url.startswith("http://") or url.startswith("https://")):
				url = "http://" + url
			self.activeBlog.find('uri').text = url

		if widget.name == 'teAcctEndpoint':
			url = widget.get_text()
			if not (url.startswith("http://") or url.startswith("https://")):
				url = "http://" + url
			self.activeBlog.find('endpoint').text = url
			
		if widget.name == 'teAcctUser':
			self.activeBlog.find('username').text = widget.get_text()

		if widget.name == 'teAcctPass':
			self.activeBlog.find('password').text = base64.b64encode(widget.get_text())

		if widget.name == 'teAcctBlogID':
			self.activeBlog.attrib['id'] = widget.get_text()

		if widget.name == 'cmbAcctSystem':		
			system = self.liststore.get_value(self.cmbAcctSystem.get_active_iter(), 1)
			self.activeBlog.find('system').text = system

		if widget.name == 'spinPullcount':
			if self.liststore.get_value(self.cmbAcctSystem.get_active_iter(), 1) == 'Blogger':
				self.activeBlog.find('pullcount').text = '25'
			else:
				self.activeBlog.find('pullcount').text = str(self.spinPullcount.get_value())[:-2]

		# We need to set up our api to match our system
		system = self.liststore.get_value(self.cmbAcctSystem.get_active_iter(), 1)
		self.activeBlog.find('api').text = systems[system]

		# We also need to update our change flag
		self.changeFlag == True


	# REMOVE ACCOUNT FUNCTIONS
	# ==================================================

	def removeAccount(self, widget, data=None):

		if len(self.accountTree) > 1:

			self.deletedBlogArray.append(self.activeBlog)
	
			self.accountTree.remove(self.activeBlog)

			
		else:
			dialog = self.dialogCreator(_('Must have at least one account'))

			dialog.destroy()

		self.populateAccountList(len(self.accountTree) - 1)

	# INTROSPECTION FUNCTIONSs
	# ==================================================

	@threaded
	def doIntrospection(self, widget, data=None):
		
		url = self.teAcctAddress.get_text()
		if not (url.startswith("http://") or url.startswith("https://")):
			url = "http://" + url

		gtk.gdk.threads_enter()
		winProgress = gtk.Window()
		#winProgress.set_property('skip-taskbar-hint', True)
		winProgress.set_transient_for(self.dlgAccounts)
		winProgress.set_position(gtk.WIN_POS_CENTER_ON_PARENT)
		winProgress.set_type_hint(gtk.gdk.WINDOW_TYPE_HINT_UTILITY)
		winProgress.set_title(_('Retrieving Blog Settings...'))
		hBox = gtk.HBox(spacing=8)
		vBox = gtk.VBox(spacing=8)
		progBar = gtk.ProgressBar()
		progBar.set_text(_('Retrieving Blog Settings...'))
		vBox.pack_start(progBar, padding=8)
		winProgress.add(hBox)
		hBox.pack_start(vBox, padding=12)
		winProgress.set_modal(True)
		winProgress.set_decorated(False)
		winProgress.resize(300, 40)
		winProgress.show_all()
		timeout = gobject.timeout_add(100, self.update_progress_bar, progBar)
		gtk.gdk.threads_leave()

		try:
			name, endpoint, blogID = self.processRSD(url)
		except Exception, e:
			print Exception, str(e)

			winProgress.destroy()

			dialog = self.dialogCreator(_('Sorry, but BloGTK could not retrieve your settings. Please enter them manually.'))

			gobject.source_remove(timeout)
			dialog.destroy()

			return False

		# Special processing for Blogspot and Blogger. The endpoint should equal the URL for the GData API.
		# Blogger's RSD points to the old API.
		if endpoint == 'http://www.blogger.com/api':
			endpoint = url

		# Well also need to know if we're dealing with Windows Live Spaces
		if endpoint == 'https://storage.msn.com/storageservice/MetaWeblog.rpc':
			name = 'Windows Live Spaces'

		# MovableType incorrectly prefers MetaWeblog to the MovableType API (!)
		# We should correct this
		if endpoint[-13:] == 'mt-xmlrpc.cgi':
			name = 'Movable Type'

		# We also need to correct for different spellings of Movable Type
		if name == 'MovableType':
			name = 'Movable Type'

		match_iter = self.search(self.liststore, self.liststore.iter_children(None), self.match_func, (1, name))
		self.cmbAcctSystem.set_active_iter(match_iter)
		self.teAcctEndpoint.set_text(endpoint)
		self.teAcctBlogID.set_text(blogID)

		# Here's where we also set our variables in the config object
		self.activeBlog.find('system').text = name
		self.activeBlog.attrib['id'] = blogID
		self.activeBlog.find('endpoint').text = endpoint

		gobject.source_remove(timeout)
		winProgress.destroy()
	
	def getIntrospectionURI(self, url):

		f = urllib2.urlopen(url)
		s = f.read()
		
		soup = BeautifulSoup(s)
		
		# If the template doesn't have RSD autodiscovery, we'll guess at
		# the RSD file location
		try:		
			rsdurl = soup.findAll(rel='EditURI')[0]['href']
		except:
			if url.endswith('/'):
				rsdurl = url + 'rsd.xml'
			else:
				rsdurl = url + '/rsd.xml'
		
		return rsdurl
		
	def processRSD(self, url):
	  
		rsdurl = self.getIntrospectionURI(url)
		
		f = urllib2.urlopen(rsdurl)
		s = f.read()
		
		doc = xml.dom.minidom.parseString(s)
		
		for api in doc.getElementsByTagName('api'):
		   if api.getAttribute('preferred') == 'true':
		      name = api.getAttribute('name')
		      endpoint = api.getAttribute('apiLink')
		      blogID = api.getAttribute('blogID')
		   else:
		      pass
		
		return name, endpoint, blogID

	def update_progress_bar(self, progBar):
		progBar.pulse()
		return True
		

	# ACCOUNT SAVING FUNCTIONS
	# ================================================== 

	def saveAccount(self, widget, data=None):

		# We need to loop through our accounts and make sure everything is filled.
		# TODO Throw a dialog here if there's an error. Also preselect the blog with the missing info

		for blog in self.accountTree.findall('blog'):
			if blog.attrib['name'] == '':
				dialog = self.dialogCreator(_('Must name your blog'))
				dialog.destroy()
				return False
			if blog.find('uri').text == '':
				dialog = self.dialogCreator(_('Must have a URI'))
				dialog.destroy()
				return False
			if blog.find('endpoint').text == '':
				dialog = self.dialogCreator(_('Must have an endpoint'))
				dialog.destroy()
				return False
			if blog.find('username').text == '':
				dialog = self.dialogCreator(_('Must have a username'))
				dialog.destroy()
				return False
			if blog.find('password').text == '':
				dialog = self.dialogCreator(_('Must have a password'))
				dialog.destroy()
				return False

		# We also need to loop through our deleted blogs array and remove any remaining cache files.
		for blog in self.deletedBlogArray:

			accountID = blog.find('endpoint').text + '/' +  blog.attrib['id']

			cacheFile = ConfigReader().configDir + '/cache/' + base64.b64encode(accountID) + ".xml"

			try:
				os.remove(cacheFile)
			except Exception, e:
				print Exception, str(e)
				

		ElementTree.ElementTree(self.accountTree).write(ConfigReader().configFile)

		# For security, we want our config file set chmod 0600 so others can't read the file.
		os.chmod(ConfigReader().configFile, 0600)

		self.mainInstance.refreshBlogList()

		self.dlgAccounts.destroy()

	# SYSTEM SETTINGS FUNCTIONS
	# ==================================================

	def setFontPreview(self, widget=None, data=None):
		

		settings = self.accountTree.find('settings')
		fontname = settings.find('editorfont').text
		self.tvFontPreview.get_buffer().set_text(fontname)
		fontdesc =  pango.FontDescription(fontname)
		self.tvFontPreview.modify_font(fontdesc)
		

	def setEditorFont(self, widget, data=None):

		settings = self.accountTree.find('settings')

		dlgSelectFont = gtk.FontSelectionDialog(_('Select Editor Font'))
		dlgSelectFont.set_icon(gtk.gdk.pixbuf_new_from_file(os.path.join(SHARED_FILES, 'res', 'b-32.png')))
		dlgSelectFont.set_transient_for(self.dlgAccounts)
		dlgSelectFont.set_font_name(settings.find('editorfont').text)
		result = dlgSelectFont.run()
		if result == gtk.RESPONSE_OK:
			fontname = dlgSelectFont.get_font_name()

			# Set our preview to display the selected font
			self.tvFontPreview.get_buffer().set_text(fontname)
			fontdesc =  pango.FontDescription(fontname)
			self.tvFontPreview.modify_font(fontdesc)

			settings.find('editorfont').text = fontname

			dlgSelectFont.destroy()

		else:
			dlgSelectFont.destroy()

	def closeWindow(self, widget, data=None):
		if self.changeFlag == True:
			msgbox = gtk.MessageDialog(parent = self.dlgAccounts, buttons = gtk.BUTTONS_OK_CANCEL, flags = gtk.DIALOG_MODAL, type = gtk.MESSAGE_WARNING, message_format = _('Are you sure you wish to close this window?'))
			msgbox.set_title("Confirm Close")
			msgbox.format_secondary_text(_('All unsaved changes will be lost.'))
			result = msgbox.run()
			msgbox.destroy()
			if result == gtk.RESPONSE_OK:
				self.dlgAccounts.destroy()
				return True
			else:
				return False
		else:
			self.dlgAccounts.destroy()
			return True

	def switchChangeFlag(self, widget, data=None):
		self.changeFlag = True


	# CONVENIENCE FUNCTIONS
	# ==================================================

	def make_pb(self, tvcolumn, cell, model, iter):
		stock = model.get_value(iter, 0)
		pb = self.cmbAcctSystem.render_icon(stock, gtk.ICON_SIZE_MENU, None)
		cell.set_property('pixbuf', pb)
		return

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
 
	def dialogCreator(self, message):
		dialog = gtk.MessageDialog(parent=self.dlgAccounts, flags=0, type=gtk.MESSAGE_ERROR, buttons=gtk.BUTTONS_OK, message_format=message)
		dialog.run()

		return dialog
