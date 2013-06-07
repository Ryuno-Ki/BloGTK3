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

import os
import base64
import time
import string

import gtk
import gtk.glade
import gnome.ui
import gobject

import feedparser

import gdata
import atom

# Internal Libraries
import config
import editor
import firstrun

class FileHandler():

	def __init__(self):
	
		return None	

	def main(self):
	
		return True

	def saveFile(self, postStruct, parentWin):

		# Our first task is to create an XML file with our post data

		postAsXML = self.postStructToXML(postStruct)

		# Now, we need to create our dialog for saving our file.
		saveFileDialog = gtk.FileChooserDialog('Save File', parentWin, gtk.FILE_CHOOSER_ACTION_SAVE)

		# We need to establish some file filters to help users narrow their choices
		saveFilter = gtk.FileFilter()
		saveFilter.add_pattern('*.blogtk')
		saveFilter.set_name('BloGTK Saved Posts')

		allFilter = gtk.FileFilter()
		allFilter.add_pattern('*')
		allFilter.set_name('All Files')

		saveFileDialog.add_filter(saveFilter)
		saveFileDialog.add_filter(allFilter)

		# Set our defaults for the save dialog
		saveFileDialog.set_do_overwrite_confirmation(True)
		saveFileDialog.add_buttons(gtk.STOCK_SAVE, gtk.RESPONSE_ACCEPT, gtk.STOCK_CANCEL, gtk.RESPONSE_REJECT)
		saveFileDialog.set_current_name('.blogtk')

		response = saveFileDialog.run()

		if response == gtk.RESPONSE_ACCEPT:
			filename = saveFileDialog.get_filename()

			try:
				saveFile = open(filename, "w")
				saveFile.write(postAsXML)
				saveFile.close()
			except Exception, e:
				saveFileDialog.destroy()
				return False, str(e)
			
			saveFileDialog.destroy()

			return True, filename
		else:
			saveFileDialog.destroy()

			return False, 'cancel'

	def resaveFile(self, postStruct, filename):

		postAsXML = self.postStructToXML(postStruct)

		try:
			saveFile = open(filename, "w")
			saveFile.write(postAsXML)
			saveFile.close()
		except Exception, e:
			return False, str(e)

		return True, filename

	def openFile(self, parentWin):
		# Now, we need to create our dialog for loading our file.
		openFileDialog = gtk.FileChooserDialog('Open File', parentWin, gtk.FILE_CHOOSER_ACTION_OPEN)

		# We need to establish some file filters to help users narrow their choices
		openFilter = gtk.FileFilter()
		openFilter.add_pattern('*.blogtk')
		openFilter.set_name('BloGTK Saved Posts')

		allFilter = gtk.FileFilter()
		allFilter.add_pattern('*')
		allFilter.set_name('All Files')

		openFileDialog.add_filter(openFilter)
		openFileDialog.add_filter(allFilter)

		# Set our defaults for the open dialog
		openFileDialog.add_buttons(gtk.STOCK_OPEN, gtk.RESPONSE_ACCEPT, gtk.STOCK_CANCEL, gtk.RESPONSE_REJECT)

		response = openFileDialog.run()
	
		if response == gtk.RESPONSE_ACCEPT:
			filename = openFileDialog.get_filename()

			try:
				openFile = open(filename, "r")
				postXML = openFile.read()
				openFile.close()

				try:
					postStruct = self.postXMLToStruct(filename)

					openFileDialog.destroy()

					return True, filename, postStruct

				except Exception, e:
					print str(Exception), str(e)
					openFileDialog.destroy()
					return False, 'Not a valid BloGTK save file'

			except Exception, e:
				print str(Exception), str(e)
				openFileDialog.destroy()
				return False, str(e)
			
			openFileDialog.destroy()

			return True, filename
		else:
			openFileDialog.destroy()

			return False, 'cancel'


	def postXMLToStruct(self, filename):

		#parser = feedparser.parse(postXML)

		tree = ElementTree.parse(filename).getroot()

		postStruct = []

		entry = tree.find('entry')
		title = entry.find('title').text
		# When we pull the XML data, it contains extra whitespace that
		# should be stripped
		content = entry.findall('content')[0].text.lstrip('\n\t\t\t').rstrip('\n\n\t\t\t')
		extended = entry.findall('content')[1].text.lstrip('\n\t\t\t').rstrip('\n\n\t\t\t')
		keywords = ''
		for index, keyword in enumerate(entry.findall('category')):
			if index != (len(entry.findall('category')) -1):
				keywords = keywords + keyword.attrib['term'] + ','
			else:
				keywords = keywords + keyword.attrib['term']
		
		postStruct.append(title)
		postStruct.append(content)
		postStruct.append(extended)
		postStruct.append(keywords)

		return postStruct
			

	def postStructToXML(self, postStruct):

		timestamp = time.strftime( "%Y-%m-%dT%H:%M:%S", time.gmtime())
			
		postAsXML = '<?xml version="1.0" encoding="utf-8" standalone="yes"?>\n\
			<feed version="0.3" xml:lang="en-US">\n\
			<title mode="escaped" type="text/html">BloGTK Generated Feed</title>\n\
			<id>BloGTK2SaveFile</id>\n\
			<modified>' + timestamp + '</modified>\n\
			<generator url="http://blogtk.sourceforge.net/" version="2.0">BloGTK</generator>\n\
			<entry>\n\
			<link href="blogtk://" rel="service.edit" title="BloGTK Saved Post File" type="application/atom+xml"/>\n\
			<author>\n\
			<name>BloGTK Saved Listing</name>\n\
			</author>\n\
			<issued>' + timestamp + '</issued>\n\
			<modified>' + timestamp + '</modified>\n\
			<created>' + timestamp + '</created>\n'

		try:
			for tag in postStruct[3].split(','):
				postAsXML = postAsXML + ' <category scheme="keyword" term="' + tag + '" />'
		except:
			pass

		# Make entry text XML safe. Yes, this is a kludge - any better ideas
		# appreciated.
		no_amps = string.replace(postStruct[1], '&', '&amp;')
		no_lts = string.replace(no_amps, '<', '&lt;')
		entry_text = string.replace(no_lts, '>', '&gt;')

		no_amps2 = string.replace(postStruct[2], '&', '&amp;')
		no_lts2 = string.replace(no_amps2, '<', '&lt;')
		extended_text = string.replace(no_lts2, '>', '&gt;')


		postAsXML = postAsXML + '<id>1</id>\n\
			<title mode="escaped" type="text/html">' + postStruct[0] + '</title>\n\
			<summary type="text/plain" mode="escaped"> </summary>\n\
			<content type="application/xhtml+xml" xml:space="preserve">\n\
			' + entry_text + '\n\
			</content>\n\
			<content type="application/xhtml+xml" xml:space="preserve">\n\
			' + extended_text + '\n\
			</content>\n\
			</entry>\n\
			</feed>'		

		return postAsXML



