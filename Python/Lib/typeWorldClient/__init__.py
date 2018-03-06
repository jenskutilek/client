# -*- coding: utf-8 -*-

import datetime
import os, sys, json, platform, urllib, urllib2, re, traceback, json, time, base64, keyring, certifi

print certifi.where()

import typeWorld.api, typeWorld.api.base
from typeWorld.api import *
from typeWorld.api.base import *

from AppKit import NSDictionary


class Preferences(object):
	pass

class JSON(Preferences):
	def __init__(self, path):
		self.path = path

	def get(self, key):
		pass

	def set(self, key, value):
		pass

	def remove(self, key, value):
		pass

	def save(self):
		pass

	def dictionary(self):
		pass


class AppKitNSUserDefaults(Preferences):
	def __init__(self, name = None):
		from AppKit import NSUserDefaults
		if name:
			self.defaults = NSUserDefaults.alloc().initWithSuiteName_(name)
		else:
			self.defaults = NSUserDefaults.standardUserDefaults()


	def get(self, key):
		if self.defaults.objectForKey_(key):
#			return json.loads(self.defaults.objectForKey_(key))

			o = self.defaults.objectForKey_(key)
#
			if 'Array' in o.__class__.__name__:
				o = list(o)

			elif 'Dictionary' in o.__class__.__name__:
				o = dict(o)

			elif 'unicode' in o.__class__.__name__:
				o = unicode(o)


#			print type(o)

			return o

	def set(self, key, value):
#		self.defaults.setObject_forKey_(json.dumps(value), key)
		
		# if type(value) == dict:
		# 	value = NSDictionary.alloc().initWithDictionary_(value)

		self.defaults.setObject_forKey_(value, key)

	def remove(self, key):
		self.defaults.removeObjectForKey_(key)

	def save(self):
		pass

	def dictionary(self):
		return dict(self.defaults.dictionaryRepresentation())



class APIClient(object):
	u"""\
	Main Type.World client app object. Use it to load repositories and install/uninstall fonts.
	"""

	def __init__(self, preferences = None):
		self.preferences = preferences
		self._publishers = {}


	def log(self, message):

		from AppKit import NSLog
		NSLog('Type.World Client: %s' % message)



	def resourceByURL(self, url, binary = False, update = False, username = None, password = None):
		u'''Caches and returns content of a HTTP resource. If binary is set to True, content will be stored and return as a bas64-encoded string'''

		resources = self.preferences.get('resources') or {}

		if not resources.has_key(url) or update:

			print 'resourceByURL', url

			request = urllib2.Request(url)
			if username and password:
				base64string = base64.b64encode(b"%s:%s" % (username, password)).decode("ascii")
				request.add_header("Authorization", "Basic %s" % base64string)   
				print 'with username and password %s:%s' % (username, password)
			response = urllib2.urlopen(request, cafile=certifi.where())


			if response.getcode() != 200:
				return False, 'Resource returned with HTTP code %s' % response.code

			else:
				content = response.read()
				if binary:
					content = base64.b64encode(content)
				resources[url] = response.headers.type + ',' + content
				self.preferences.set('resources', resources)

				return True, content, response.headers.type

		else:

			response = resources[url]
			mimeType = response.split(',')[0]
			content = response[len(mimeType)+1:]


			return True, content, mimeType


	def readJSONResponse(self, url, acceptableMimeTypes):
		d = {}
		d['errors'] = []
		d['warnings'] = []
		d['information'] = []

		# Validate
		api = typeWorld.api.APIRoot()

		try:
			request = urllib2.Request(url)
			response = urllib2.urlopen(request, cafile=certifi.where())

			if response.getcode() != 200:
				d['errors'].append('Resource returned with HTTP code %s' % response.code)

			if not response.headers.type in acceptableMimeTypes:
				d['errors'].append('Resource headers returned wrong MIME type: "%s". Expected is %s.' % (response.headers.type, acceptableMimeTypes))
				self.log('Received this response with an unexpected MIME type for the URL %s:\n\n%s' % (url, response.read()))

			if response.getcode() == 200:

				api.loadJSON(response.read())

				information, warnings, errors = api.validate()

				if information:
					d['information'].extend(information)
				if warnings:
					d['warnings'].extend(warnings)
				if errors:
					d['errors'].extend(errors)

		except:
			exc_type, exc_value, exc_traceback = sys.exc_info()
			for line in traceback.format_exception_only(exc_type, exc_value):
				d['errors'].append(line)

		return api, d

	def readGitHubResponse(self, url, username = None, password = None):

		d = {}
		d['errors'] = []
		d['warnings'] = []
		d['information'] = []

		json = ''

		try:

			print 'readGitHubResponse(%s)' % url

			request = urllib2.Request(url)
			if username and password:
				base64string = base64.b64encode(b"%s:%s" % (username, password)).decode("ascii")
				request.add_header("Authorization", "Basic %s" % base64string)   
			response = urllib2.urlopen(request, cafile=certifi.where())

			if response.getcode() == 404:
				d['errors'].append('Server returned with error 404 (Not found). This hints at wring username or password.')
				return None, d

			if response.getcode() == 401:
				d['errors'].append('User authentication failed. Please review your username and password.')
				return None, d

			if response.getcode() != 200:
				d['errors'].append('Resource returned with HTTP code %s' % response.code)

			# if not response.headers.type in acceptableMimeTypes:
			# 	d['errors'].append('Resource headers returned wrong MIME type: "%s". Expected is %s.' % (response.headers.type, acceptableMimeTypes))
			# 	self.log('Received this response with an unexpected MIME type for the URL %s:\n\n%s' % (url, response.read()))

			if response.getcode() == 200:

				json = response.read()

		except:
			exc_type, exc_value, exc_traceback = sys.exc_info()
			for line in traceback.format_exception_only(exc_type, exc_value):
				d['errors'].append(line)
			self.log(traceback.format_exc())

		return json, d


	def addAttributeToURL(self, url, key, value):
		if not key + '=' in url:
			if '?' in url:
				url += '&' + key + '=' + value
			else:
				url += '?' + key + '=' + value
		else:
			url = re.sub(key + '=(\w*)', key + '=' + value, url)

		return url

	def anonymousAppID(self):
		anonymousAppID = self.preferences.get('anonymousAppID')

		if anonymousAppID == None or anonymousAppID == {}:
			import uuid
			anonymousAppID = str(uuid.uuid1())
			self.preferences.set('anonymousAppID', anonymousAppID)


		return anonymousAppID


	def addSubscription(self, url, username = None, password = None):

		if url.startswith('typeworldjson://'):

			url = url.replace('typeworldjson://', '')

			# Read response
			api, responses = self.readJSONResponse(url, INSTALLABLEFONTSCOMMAND['acceptableMimeTypes'])

			# Errors
			if responses['errors']:
				return False, '\n'.join(responses['errors']), None

			# Check for installableFonts response support
			if not 'installableFonts' in api.supportedCommands and not 'installFonts' in api.supportedCommands:
				return False, 'API endpoint %s does not support the "installableFonts" and "installFonts" commands.' % api.canonicalURL, None

			# Tweak url to include "installableFonts" command
			url = self.addAttributeToURL(url, 'command', 'installableFonts')

			# Read response again, this time with installableFonts command
			api, responses = self.readJSONResponse(url, INSTALLABLEFONTSCOMMAND['acceptableMimeTypes'])

			publisher = self.publisher(api.canonicalURL)
			publisher.set('type', 'JSON')
			success, message = publisher.addJSONSubscription(url, api)
			publisher.save()

			return success, message, self.publisher(api.canonicalURL)

		elif url.startswith('typeworldgithub://'):


			url = url.replace('typeworldgithub://', '')
			# remove trailing slash
			while url.endswith('/'):
				url = url[:-1]
			
			if not url.startswith('https://'):
				return False, 'GitHub-URL needs to start with https://', None

			canonicalURL = '/'.join(url.split('/')[:4])
			owner = url.split('/')[3]
			repo = url.split('/')[4]
			path = '/'.join(url.split('/')[7:])


			commitsURL = 'https://api.github.com/repos/%s/%s/commits?path=%s' % (owner, repo, path)


			publisher = self.publisher(canonicalURL)
			publisher.set('type', 'GitHub')

			if username and password:
				publisher.set('username', username)
				publisher.setPassword(username, password)

			allowed, message = publisher.gitHubRateLimit()
			if not allowed:
				return False, message, None

			# Read response
			commits, responses = publisher.readGitHubResponse(commitsURL)

			# Errors
			if responses['errors']:
				return False, '\n'.join(responses['errors']), None

			success, message = publisher.addGitHubSubscription(url, commits)
			publisher.save()

			return success, message, self.publisher(canonicalURL)

		else:
			return False, 'Unknown protocol, known are: %s' % (typeWorld.api.base.PROTOCOLS), None


	def publisher(self, canonicalURL):
		if not self._publishers.has_key(canonicalURL):
			e = APIPublisher(self, canonicalURL)
			self._publishers[canonicalURL] = e

		if self.preferences.get('publishers') and canonicalURL in self.preferences.get('publishers'):
			self._publishers[canonicalURL].exists = True

		return self._publishers[canonicalURL]

	def publishers(self):
		if self.preferences.get('publishers'):
			return [self.publisher(canonicalURL) for canonicalURL in self.preferences.get('publishers')]
		else:
			return []


class APIPublisher(object):
	u"""\
	Represents an API endpoint, identified and grouped by the canonical URL attribute of the API responses. This API endpoint class can then hold several repositories.
	"""

	def __init__(self, parent, canonicalURL):
		self.parent = parent
		self.canonicalURL = canonicalURL
		self.exists = False
		self._subscriptions = {}

	def gitHubRateLimit(self):

		limits, responses = self.readGitHubResponse('https://api.github.com/rate_limit')

		if responses['errors']:
			return False, '\n'.join(responses['errors'])

		limits = json.loads(limits)

		if limits['rate']['remaining'] == 0:
			return False, 'Your GitHub API rate limit has been reached. The limit resets at %s.' % (datetime.datetime.fromtimestamp(limits['rate']['reset']).strftime('%Y-%m-%d %H:%M:%S'))

		return True, None


	def readGitHubResponse(self, url):

		if self.get('username') and self.getPassword(self.get('username')):
			return self.parent.readGitHubResponse(url, self.get('username'), self.getPassword(self.get('username')))
		else:
			return self.parent.readGitHubResponse(url)


	def name(self, locale = ['en']):

		if self.get('type') == 'JSON':
			return self.subscriptions()[0].latestVersion().name.getTextAndLocale(locale = locale)
		else:

			url = 'https://api.github.com/users/%s' % self.canonicalURL.split('/')[-1]
			success, content, mimeType = self.resourceByURL(url)
			if success:
				userInfo = json.loads(content)
				return userInfo['name'], 'en'

			else:
				return 'Error', 'en'

	def getPassword(self, username):
		return keyring.get_password("Type.World GitHub Subscription %s (%s)" % (self.canonicalURL, username), username)

	def setPassword(self, username, password):
		keyring.set_password("Type.World GitHub Subscription %s (%s)" % (self.canonicalURL, username), username, password)

	def resourceByURL(self, url, binary = False, update = False):
		u'''Caches and returns content of a HTTP resource. If binary is set to True, content will be stored and return as a bas64-encoded string'''

		# Save resource
		resourcesList = self.get('resources') or []
		if not url in resourcesList:
			resourcesList.append(url)
			self.set('resources', resourcesList)

		if self.get('username') and self.getPassword(self.get('username')):
			return self.parent.resourceByURL(url, binary = binary, update = update, username = self.get('username'), password = self.getPassword(self.get('username')))
		else:
			return self.parent.resourceByURL(url, binary = binary, update = update)

	def amountInstalledFonts(self):
		amount = 0
		# Get font

		for subscription in self.subscriptions():
			amount += subscription.amountInstalledFonts()

		return amount

	def currentSubscription(self):
		if self.get('currentSubscription'):
			subscription = self.subscription(self.get('currentSubscription'))
			if subscription:
				return subscription
			else:
				return self.subscriptions()[0]

	def get(self, key):
		preferences = dict(self.parent.preferences.get(self.canonicalURL) or self.parent.preferences.get('publisher(%s)' % self.canonicalURL) or {})
		if preferences.has_key(key):

			o = preferences[key]

			if 'Array' in o.__class__.__name__:
				o = list(o)

			elif 'Dictionary' in o.__class__.__name__:
				o = dict(o)

			return o

	def set(self, key, value):
		preferences = dict(self.parent.preferences.get(self.canonicalURL) or self.parent.preferences.get('publisher(%s)' % self.canonicalURL) or {})
		preferences[key] = value
		self.parent.preferences.set('publisher(%s)' % self.canonicalURL, preferences)

	def path(self):
		from os.path import expanduser
		home = expanduser("~")
		return os.path.join(home, 'Library', 'Fonts', 'Type.World App', '%s (%s)' % (self.name()[0], self.get('type')))

	def addJSONSubscription(self, url, api):

		self.parent._subscriptions = {}

		subscription = self.subscription(url)

		subscription.addJSONVersion(api)
		self.set('currentSubscription', url)
		subscription.save()

		return True, None

	def addGitHubSubscription(self, url, commits):

		self.parent._subscriptions = {}

		subscription = self.subscription(url)
		subscription.set('commits', commits)
		self.set('currentSubscription', url)
		subscription.save()

		return True, None


	def subscription(self, url):
		if not self._subscriptions.has_key(url):
			e = APISubscription(self, url)
			self._subscriptions[url] = e

		if self.get('subscriptions') and url in self.get('subscriptions'):
			self._subscriptions[url].exists = True

		return self._subscriptions[url]

	def subscriptions(self):
		return [self.subscription(url) for url in self.get('subscriptions') or []]

	def update(self):
		for subscription in self.subscriptions():
			success, message = subscription.update()
			if not success:
				return success, message

		return True, None

	def save(self):
		publishers = self.parent.preferences.get('publishers') or []
		if not self.canonicalURL in publishers:
			publishers.append(self.canonicalURL)
		self.parent.preferences.set('publishers', publishers)

	def delete(self):

		for subscription in self.subscriptions():
			subscription.delete(calledFromParent = True)

		# Path
		try:
			os.rmdir(self.path())
		except:
			pass

		# Old
		self.parent.preferences.remove(self.canonicalURL)
		# New
		self.parent.preferences.remove('publisher(%s)' % self.canonicalURL)

		# Resources
		resources = self.parent.preferences.get('resources') or {}
		for url in self.get('resources') or []:
			if resources.has_key(url):
				del resources[url]
		self.parent.preferences.set('resources', resources)


		publishers = self.parent.preferences.get('publishers')
		publishers.remove(self.canonicalURL)
		self.parent.preferences.set('publishers', publishers)
		self.parent.preferences.set('currentPublisher', '')

		self.parent._publishers = {}

class APIFont(object):
	def __init__(self, parent, twObject = None, gitHubContent = None):
		self.parent = parent
		self.twObject = twObject
		self.gitHubContent = gitHubContent

		# Init attributes
		self.keywords = ['beta', 'free', 'licenseAllowanceDescription', 'licenseKeyword', 'name', 'postScriptName', 'previewImage', 'purpose', 'requiresUserID', 'seatsAllowedForUser', 'seatsInstalledByUser', 'timeAddedForUser', 'timeFirstPublished', 'format', 'uniqueID', 'upgradeLicenseURL', 'variableFont', 'setName', 'versions']
		for keyword in self.keywords:
			setattr(self, keyword, None)

		# Take data from twObject
		if self.twObject:
			for keyword in self.keywords:
				setattr(self, keyword, getattr(self.twObject, keyword))

		if self.gitHubContent:
			self.postScriptName = self.gitHubContent['name'].split('.')[0]
			self.name = typeWorld.api.MultiLanguageText()
			self.name.en = self.postScriptName.split('-')[1]
			self.purpose = 'desktop'
			self.format = self.gitHubContent['name'].split('.')[-1]
			self.uniqueID = self.gitHubContent['name']

			# set name
			self.setName = typeWorld.api.MultiLanguageText()
			if len(self.postScriptName.split('-')[0]) > len(self.parent.parent.parent.name()):
				self.setName.en = self.postScriptName.split('-')[0][len(self.parent.name())+1:]


	def delete(self):
		self.parent.parent.parent.removeFont(self.uniqueID)


	def getSortedVersions(self):
		if self.twObject:
			return self.twObject.getSortedVersions()

		elif self.gitHubContent:

			owner = self.parent.parent.parent.url.split('/')[3]
			repo = self.parent.parent.parent.url.split('/')[4]
			path = '/'.join(self.parent.parent.parent.url.split('/')[7:])

			# commitsURL = 'https://api.github.com/repos/%s/%s/commits?path=%s/fonts/%s.%s' % (owner, repo, path, self.postScriptName, self.format)
			# print 'commitsURL', commitsURL

			# # Read response
			# commits, responses = self.parent.parent.parent.parent.parent.readGitHubResponse(commitsURL)
			# commits = json.loads(commits)
			# if commits.has_key('message'):
			# 	return []

			commits = self.parent.parent.parent.get('commits')
			commits = reversed(json.loads(commits))



			
			versions = []
			for commit in commits:

				if 'version' in commit['commit']['message'].lower() and ':' in commit['commit']['message']:
					number = commit['commit']['message'].split('\n')[0].split(':')[1].strip()
					newVersion = typeWorld.api.Version()
					newVersion.number = number
					versions.append(newVersion)
			return versions



	def filename(self, version):
		return '%s_%s.%s' % (self.uniqueID, version, self.format)

	def path(self, version, folder = None):

		# User fonts folder
		if not folder:
			folder = self.parent.parent.parent.parent.path()
			
		return os.path.join(folder, self.filename(version))


class APIFamily(object):
	def __init__(self, parent, twObject = None):
		self.parent = parent
		self.twObject = twObject

		# Init attributes
		self.keywords = ['billboards', 'description', 'issueTrackerURL', 'name', 'sourceURL', 'timeFirstPublished', 'uniqueID', 'upgradeLicenseURL']
		for keyword in self.keywords:
			setattr(self, keyword, None)

		# Take data from twObject
		if self.twObject:
			for keyword in self.keywords:
				setattr(self, keyword, getattr(self.twObject, keyword))

		# GitHub
		if self.parent.parent.parent.get('type') == 'GitHub':

			self.name = typeWorld.api.MultiLanguageText()
			self.name.en = self.parent.parent.name()
			self.uniqueID = self.parent.parent.name()
			self.sourceURL = self.parent.parent.url

			return

			url = 'https://api.github.com/users/%s' % self.parent.parent.parent.canonicalURL.split('/')[-1]
			success, content, mimeType = self.parent.parent.parent.resourceByURL(url)
			if success:
				userInfo = json.loads(content)
				self.name = typeWorld.api.MultiLanguageText()
				self.name.en = userInfo['name']
				self.logo = userInfo['avatar_url']
				self.website = userInfo['html_url']
				if userInfo['email']: 
					self.email = userInfo['email']
				if userInfo['bio']: 
					self.description = typeWorld.api.MultiLanguageText()
					self.description.en = userInfo['bio']

	def gitHubFonts(self):


		if not hasattr(self, '_githubfonts'):

			print 'gitHubFonts()'

			url = self.parent.parent.url
			owner = url.split('/')[3]
			repo = url.split('/')[4]
			path = '/'.join(url.split('/')[7:]) + '/fonts'

			
			# owner = self.parent.parent.parent.canonicalURL.split('/')[-1]
			# repo = self.parent.parent.url.split('/')[-1]
			# path = '/'.join(self.parent.parent.url.split('/')[-2:-1])

			url = 'https://api.github.com/repos/%s/%s/contents/%s' % (owner, repo, path)

			if self.parent.parent.parent.get('username') and self.parent.parent.parent.getPassword(self.parent.parent.parent.get('username')):
				success, content, mimeType = self.parent.parent.parent.parent.resourceByURL(url, username = self.parent.parent.parent.get('username'), password = self.parent.parent.parent.getPassword(self.parent.parent.parent.get('username')))
			else:
				success, content, mimeType = self.parent.parent.parent.parent.resourceByURL(url)

	#		success, content, mimeType = self.parent.parent.parent.resourceByURL(url)

			self._githubfonts = json.loads(content)

		return self._githubfonts

	def fonts(self):

		fonts = []

		if self.parent.parent.parent.get('type') == 'JSON':
			for font in self.twObject.fonts:
				newFont = APIFont(self, font)
				fonts.append(newFont)

		elif self.parent.parent.parent.get('type') == 'GitHub':

			for font in self.gitHubFonts():
				newFont = APIFont(self, gitHubContent = font)
				fonts.append(newFont)

		return fonts


	def versions(self):

		return self.twObject.versions

	def setNames(self, locale):
		setNames = []
		for font in self.fonts():
			if not font.setName.getText(locale) in setNames:
				setNames.append(font.setName.getText(locale))
		return setNames

	def formatsForSetName(self, setName, locale):
		formats = []
		for font in self.fonts():
			if font.setName.getText(locale) == setName:
				if not font.format in formats:
					formats.append(font.format)
		return formats



class APIFoundry(object):
	def __init__(self, parent, twObject = None):
		self.parent = parent
		self.twObject = twObject

		self._families = []

		# Init attributes
		self.keywords = ['backgroundColor', 'description', 'email', 'facebook', 'instagram', 'logo', 'name', 'skype', 'supportEmail', 'telephone', 'twitter', 'website']
		for keyword in self.keywords:
			setattr(self, keyword, None)

		# Take data from twObject
		if self.twObject:
			for keyword in self.keywords:
				setattr(self, keyword, getattr(self.twObject, keyword))

		# GitHub
		if self.parent.parent.get('type') == 'GitHub':
			url = 'https://api.github.com/users/%s' % self.parent.parent.canonicalURL.split('/')[-1]
			success, content, mimeType = self.parent.parent.resourceByURL(url)
			if success:
				userInfo = json.loads(content)
				self.name = typeWorld.api.MultiLanguageText()
				self.name.en = userInfo['name']
				self.logo = userInfo['avatar_url']
				self.website = userInfo['html_url']
				if userInfo['email']: 
					self.email = userInfo['email']
				if userInfo['bio']: 
					self.description = typeWorld.api.MultiLanguageText()
					self.description.en = userInfo['bio']


	def families(self):

		if not self._families:

			if self.parent.parent.get('type') == 'JSON':
				for family in self.twObject.families:
					newFamily = APIFamily(self, family)
					self._families.append(newFamily)

			elif self.parent.parent.get('type') == 'GitHub':
				newFamily = APIFamily(self)
				self._families.append(newFamily)

		return self._families


class APISubscription(object):
	u"""\
	Represents an API endpoint, identified and grouped by the canonical URL attribute of the API responses. This API endpoint class can then hold several repositories.
	"""

	def __init__(self, parent, url):
		self.parent = parent
		self.url = url
		self.exists = False

		self._foundries = []

		self.versions = []
		if self.get('versions'):
			for dictData in self.get('versions'):
				api = APIRoot()
				api.parent = self
				api.loadJSON(dictData)
				self.versions.append(api)

		

	def name(self, locale = ['en']):

		if self.parent.get('type') == 'JSON':
			return self.latestVersion().response.getCommand().name.getText(locale) or '#(Undefined)'
		if self.parent.get('type') == 'GitHub':
			return self.url.split('/')[-1]


	def resourceByURL(self, url, binary = False, update = False):
		u'''Caches and returns content of a HTTP resource. If binary is set to True, content will be stored and return as a bas64-encoded string'''

		# Save resource
		resourcesList = self.get('resources') or []
		if not url in resourcesList:
			resourcesList.append(url)
			self.set('resources', resourcesList)

		if self.parent.get('username') and self.parent.getPassword(self.get('username')):
			return self.parent.parent.resourceByURL(url, binary, self.parent.get('username'), self.parent.getPassword(self.get('username')))
		else:
			return self.parent.parent.resourceByURL(url, binary)



	def familyByID(self, ID):

		for foundry in self.foundries():
			for family in foundry.families():
				if family.uniqueID == ID:
					return family


	def fontByID(self, ID):

		for foundry in self.foundries():
			for family in foundry.families():
				for font in family.fonts():
					if font.uniqueID == ID:
						return font

	def subscription(self, url):
		if not self._subscriptions.has_key(url):
			e = APISubscription(self, url)
			self._subscriptions[url] = e

		if self.get('subscriptions') and url in self.get('subscriptions'):
			self._subscriptions[url].exists = True

		return self._subscriptions[url]

	def subscriptions(self):
		return [self.subscription(url) for url in self.get('subscriptions') or []]



	def foundries(self):

		if not self._foundries:

			if self.parent.get('type') == 'JSON':
				for foundry in self.latestVersion().response.getCommand().foundries:

					newFoundry = APIFoundry(self, twObject = foundry)

					self._foundries.append(newFoundry)

			elif self.parent.get('type') == 'GitHub':

				newFoundry = APIFoundry(self)
				self._foundries.append(newFoundry)


		return self._foundries


	def amountInstalledFonts(self):
		amount = 0
		# Get font
		for foundry in self.foundries():
			for family in foundry.families():
				for font in family.fonts():
					if self.installedFontVersion(font.uniqueID):
						amount += 1
		return amount

	def installedFontVersion(self, fontID = None, folder = None):

		api = self.latestVersion()

		for foundry in self.foundries():
			for family in foundry.families():
				for font in family.fonts():
					if font.uniqueID == fontID:

						for version in font.getSortedVersions():
#							print 'installedFontVersion ', font.path(version.number, folder)
							if os.path.exists(font.path(version.number, folder)):
								return version.number

	def removeFont(self, fontID, folder = None):


		# Get font
		for foundry in self.foundries():
			for family in foundry.families():
				for font in family.fonts():
					if font.uniqueID == fontID:

						if font.requiresUserID:
						
							api = self.latestVersion()

							# Build URL
							url = self.url
							url = self.parent.parent.addAttributeToURL(url, 'command', 'uninstallFont')
							url = self.parent.parent.addAttributeToURL(url, 'fontID', urllib.quote_plus(fontID))
							url = self.parent.parent.addAttributeToURL(url, 'anonymousAppID', self.parent.parent.anonymousAppID())

							print 'Uninstalling %s in %s' % (fontID, folder)
							print url

							acceptableMimeTypes = UNINSTALLFONTCOMMAND['acceptableMimeTypes']

							try:
								request = urllib2.Request(url)
								response = urllib2.urlopen(request, cafile=certifi.where())

								if response.getcode() != 200:
									return False, 'Resource returned with HTTP code %s' % response.code

								if not response.headers.type in acceptableMimeTypes:
									return False, 'Resource headers returned wrong MIME type: "%s". Expected is %s.' % (response.headers.type, acceptableMimeTypes)


								api = APIRoot()
								_json = response.read()
								api.loadJSON(_json)

								# print _json

								if api.response.getCommand().type == 'error':
									return False, api.response.getCommand().errorMessage
								elif api.response.getCommand().type == 'seatAllowanceReached':
									return False, 'seatAllowanceReached'
								

								# REMOVE
								installedFontVersion = self.installedFontVersion(font.uniqueID)

								if installedFontVersion:
									# Delete file
									path = font.path(installedFontVersion, folder)


									if os.path.exists(path):
										os.remove(path)

								return True, None


							except:
								exc_type, exc_value, exc_traceback = sys.exc_info()
								return False, traceback.format_exc()

						else:
							# REMOVE
							installedFontVersion = self.installedFontVersion(font.uniqueID)

							if installedFontVersion:
								# Delete file

								path = font.path(installedFontVersion, folder)

								if os.path.exists(path):
									os.remove(path)

							return True, None
							
		return True, ''


	def installFont(self, fontID, version, folder = None):

		if self.parent.get('type') == 'JSON':

			api = self.latestVersion()


			# Get font
			for foundry in self.foundries():
				for family in foundry.families():
					for font in family.fonts():
						if font.uniqueID == fontID:
							
							# Build URL
							url = self.url
							url = self.parent.parent.addAttributeToURL(url, 'command', 'installFont')
							url = self.parent.parent.addAttributeToURL(url, 'fontID', urllib.quote_plus(fontID))
							url = self.parent.parent.addAttributeToURL(url, 'anonymousAppID', self.parent.parent.anonymousAppID())
							url = self.parent.parent.addAttributeToURL(url, 'fontVersion', str(version))

							print 'Installing %s in %s' % (fontID, folder)
							print url

							acceptableMimeTypes = INSTALLFONTCOMMAND['acceptableMimeTypes']

							try:
								request = urllib2.Request(url)
								response = urllib2.urlopen(request, cafile=certifi.where())

								if response.getcode() != 200:
									return False, 'Resource returned with HTTP code %s' % response.code

								if not response.headers.type in acceptableMimeTypes:
									return False, 'Resource headers returned wrong MIME type: "%s". Expected is %s.' % (response.headers.type, acceptableMimeTypes)

								# Expect an error message
								if response.headers.type == 'application/json':

									api = APIRoot()
									_json = response.read()
									api.loadJSON(_json)

									# Validation
									information, warnings, errors = api.validate()
									if errors:
										return False, '\n\n'.join(errors)

									if api.response.getCommand().type == 'error':
										return False, api.response.getCommand().errorMessage
									elif api.response.getCommand().type == 'seatAllowanceReached':
										return False, 'seatAllowanceReached'
									elif api.response.getCommand().type == 'success':
									

										# Write file
										path = font.path(version, folder)

										# Create folder if it doesn't exist
										if not os.path.exists(os.path.dirname(path)):
											os.makedirs(os.path.dirname(path))

										# Put future encoding switches here
										f = open(path, 'wb')
										f.write(base64.b64decode(api.response.getCommand().font))
										f.close()

										return True, None

								else:

									return False, "Unsupported MIME type (%s)." % (response.headers.type)

							except:
								exc_type, exc_value, exc_traceback = sys.exc_info()
								return False, traceback.format_exc()


		elif self.parent.get('type') == 'GitHub':

			allowed, message = self.parent.gitHubRateLimit()
			if allowed:

				# Get font
				for foundry in self.foundries():
					for family in foundry.families():
						for font in family.fonts():
							if font.uniqueID == fontID:

								for commit in json.loads(self.get('commits')):
									if commit['commit']['message'].startswith('Version: %s' % version):
										print 'Install version %s, commit %s' % (version, commit['sha'])

										owner = self.url.split('/')[3]
										repo = self.url.split('/')[4]
										urlpath = '/'.join(self.url.split('/')[7:]) + '/fonts/' + font.postScriptName + '.' + font.format


										url = 'https://api.github.com/repos/%s/%s/contents/%s?ref=%s' % (owner, repo, urlpath, commit['sha'])
										print url
										response, responses = self.parent.readGitHubResponse(url)
										response = json.loads(response)


										# Write file
										path = font.path(version, folder)

										# Create folder if it doesn't exist
										if not os.path.exists(os.path.dirname(path)):
											os.makedirs(os.path.dirname(path))

										f = open(path, 'wb')
										f.write(base64.b64decode(response['content']))
										f.close()

										return True, None
			else:
				return False, message



		return False, 'No font was found to install.'

	def latestVersion(self):
		if self.versions:
			return self.versions[-1]

	def update(self):

		# reset
		self._foundries = []

		if self.parent.get('type') == 'JSON':
			api, responses = self.parent.parent.readJSONResponse(self.url, INSTALLABLEFONTSCOMMAND['acceptableMimeTypes'])
			if responses['errors']:
				return False, '\n'.join(responses['errors'])
			self.addJSONVersion(api)

		elif self.parent.get('type') == 'GitHub':

			owner = self.url.split('/')[3]
			repo = self.url.split('/')[4]
			path = '/'.join(self.url.split('/')[7:])

			commitsURL = 'https://api.github.com/repos/%s/%s/commits?path=%s/fonts' % (owner, repo, path)
			print 'commitsURL', commitsURL

			# Read response
			commits, responses = self.parent.readGitHubResponse(commitsURL)
			self.set('commits', commits)


		return True, None


	def get(self, key):
		preferences = dict(self.parent.parent.preferences.get(self.url) or self.parent.parent.preferences.get('subscription(%s)' % self.url) or {})
		if preferences.has_key(key):

			o = preferences[key]

			if 'Array' in o.__class__.__name__:
				o = list(o)

			elif 'Dictionary' in o.__class__.__name__:
				o = dict(o)

			return o

	def set(self, key, value):
		preferences = dict(self.parent.parent.preferences.get(self.url) or self.parent.parent.preferences.get('subscription(%s)' % self.url) or {})
		preferences[key] = value
		self.parent.parent.preferences.set('subscription(%s)' % self.url, preferences)

	def save(self):
		subscriptions = self.parent.get('subscriptions') or []
		if not self.url in subscriptions:
			subscriptions.append(self.url)
		self.parent.set('subscriptions', subscriptions)

		self.set('versions', [x.dumpJSON() for x in self.versions])

	def addJSONVersion(self, api):
		if self.versions:
			self.versions[-1] = api
		else:
			self.versions = [api]

		self.save()



	def delete(self, calledFromParent = False):


		for foundry in self.foundries():
			for family in foundry.families():
				for font in family.fonts():
					font.delete()


		# Resources
		resources = self.parent.parent.preferences.get('resources') or {}
		for url in self.get('resources') or []:
			if resources.has_key(url):
				print 'Deleting resource', url
				resources.pop(url)
		self.parent.parent.preferences.set('resources', resources)


		if self.parent.get('currentSubscription') == self.url:
			self.parent.set('currentSubscription', '')

		# Old
		self.parent.parent.preferences.remove(self.url)
		# New
		self.parent.parent.preferences.remove('subscription(%s)' % self.url)

		# Resources
		resources = self.parent.parent.preferences.get('resources') or {}
		for url in self.get('resources') or []:
			if resources.has_key(url):
				del resources[url]
		self.parent.parent.preferences.set('resources', resources)

		subscriptions = self.parent.get('subscriptions')
		subscriptions.remove(self.url)
		self.parent.set('subscriptions', subscriptions)

		if len(subscriptions) == 0 and calledFromParent == False:
			self.parent.delete()

		self.parent._subscriptions = {}


if __name__ == '__main__':

	client = APIClient(preferences = AppKitNSUserDefaults('world.type.clientapp'))

	print client.addSubscription('typeworldgithub://https://github.com/typeWorld/sampleGithubSubscription/tree/master/fontFamilies/YanoneKaffeesatz')

# 	for endpoint in client.publishers():
# 		print endpoint
# 		for subscription in endpoint.subscriptions():
# 			print subscription.latestVersion()
# #			subscription.update()
