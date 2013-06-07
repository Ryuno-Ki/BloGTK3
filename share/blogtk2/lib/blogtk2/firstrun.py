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

import os


# Internal Libraries
import config


configdir = '/.BloGTK'



def threaded(f):
    def wrapper(*args):
        t = threading.Thread(target=f, args=args)
        t.start()
    return wrapper

class BloGTKFirstRun():

	def __init__(self, mainInstance):
		self.mainInstance = mainInstance

	def checkConfigStatus(self):
		if os.path.exists(os.path.expanduser('~') + configdir) == 1:
			# If the config file does not exist within this directory, create it:
			if os.path.isfile(os.path.expanduser('~') + configdir + '/config.xml') != 1:
				self.createConfigFile()
			# If no cache directory, create it
			if os.path.exists(os.path.expanduser('~') + configdir + '/cache') != 1:
				os.mkdir(os.path.expanduser('~') + configdir + '/cache')
			
		else:
			# Create our configuration data directories
			os.mkdir(os.path.expanduser('~') + configdir)
			os.mkdir(os.path.expanduser('~') + configdir + '/cache')
			#Ensure our newly created directories are not readable by other users.
			os.chmod(os.path.expanduser('~') + configdir, 0700)
			self.createConfigFile()

	def createConfigFile(self):
		self.configFilePath = os.path.expanduser('~') + configdir + '/config.xml'

		conf = open(self.configFilePath, "w")
		conf.write('<blogtk>\
		<blog id="1" name="My First Blog">\
		<uri>http://www.myblog.com/</uri>\
		<endpoint>http://www.myblog.com/</endpoint>\
		<api>gdata</api>\
		<system>Blogger</system>\
		<username>user@gmail.com</username>\
		<password> </password>\
		<pullcount>20</pullcount>\
		</blog>\
		<settings>\
		<editorfont>Sans 10</editorfont>\
		</settings>\
		</blogtk>')
		conf.close()
		config.ConfigGUI(self.mainInstance)
