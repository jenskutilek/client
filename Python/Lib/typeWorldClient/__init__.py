# -*- coding: utf-8 -*-


import os, sys, json, platform, urllib, urllib2, re, traceback, json, time, base64

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


	def resourceByURL(self, url, binary = False):
		u'''Caches and returns content of a HTTP resource. If binary is set to True, content will be stored and return as a bas64-encoded string'''

		resources = self.preferences.get('resources') or {}

		if not resources.has_key(url):

			response = urllib2.urlopen(url)

			if response.getcode() != 200:
				return False, 'Resource returned with HTTP code %s' % response.code

			else:
				content = response.read()
				if binary:
					content = base64.b64encode(content)
				resources[url] = content
				self.preferences.set('resources', resources)

				return True, content

		else:
			return True, resources[url]


	def readResponse(self, url, acceptableMimeTypes):
		d = {}
		d['errors'] = []
		d['warnings'] = []
		d['information'] = []

		# Validate
		api = typeWorld.api.APIRoot()

		try:
			response = urllib2.urlopen(url)

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

	def addSubscription(self, url):

		# Read response
		api, responses = self.readResponse(url, INSTALLABLEFONTSCOMMAND['acceptableMimeTypes'])

		# Errors
		if responses['errors']:
			return False, '\n'.join(responses['errors']), None

		# Check for installableFonts response support
		if not 'installableFonts' in api.supportedCommands and not 'installFonts' in api.supportedCommands:
			return False, 'API endpoint %s does not support the "installableFonts" and "installFonts" commands.' % api.canonicalURL, None

		# Tweak url to include "installableFonts" command
		url = self.addAttributeToURL(url, 'command', 'installableFonts')

		# Read response again, this time with installableFonts command
		api, responses = self.readResponse(url, INSTALLABLEFONTSCOMMAND['acceptableMimeTypes'])

		publisher = self.publisher(api.canonicalURL)
		success, message = publisher.addSubscription(url, api)
		publisher.save()

		return success, message, self.publisher(api.canonicalURL)

	def publisher(self, canonicalURL):
		if not self._publishers.has_key(canonicalURL):
			e = APIPublisher(self, canonicalURL)
			self._publishers[canonicalURL] = e

		if self.preferences.get('JSONPublishers') and canonicalURL in self.preferences.get('JSONPublishers'):
			self._publishers[canonicalURL].exists = True

		return self._publishers[canonicalURL]

	def publishers(self):
		if self.preferences.get('JSONPublishers'):
			return [self.publisher(canonicalURL) for canonicalURL in self.preferences.get('JSONPublishers')]
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
		preferences = dict(self.parent.preferences.get(self.canonicalURL) or self.parent.preferences.get('JSONPublisher(%s)' % self.canonicalURL) or {})
		if preferences.has_key(key):

			o = preferences[key]

			if 'Array' in o.__class__.__name__:
				o = list(o)

			elif 'Dictionary' in o.__class__.__name__:
				o = dict(o)

			return o

	def set(self, key, value):
		preferences = dict(self.parent.preferences.get(self.canonicalURL) or self.parent.preferences.get('JSONPublisher(%s)' % self.canonicalURL) or {})
		preferences[key] = value
		self.parent.preferences.set('JSONPublisher(%s)' % self.canonicalURL, preferences)

	def path(self):
		from os.path import expanduser
		home = expanduser("~")
		return os.path.join(home, 'Library', 'Fonts', 'Type.World App', self.subscriptions()[0].latestVersion().name.getText('en'))

	def addSubscription(self, url, api):

		self.parent._subscriptions = {}

		subscription = self.subscription(url)
		subscription.addVersion(api)
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
		publishers = self.parent.preferences.get('JSONPublishers') or []
		if not self.canonicalURL in publishers:
			publishers.append(self.canonicalURL)
		self.parent.preferences.set('JSONPublishers', publishers)

	def delete(self):

		for subscription in self.subscriptions():
			subscription.delete(calledFromParent = True)

		# Old
		self.parent.preferences.remove(self.canonicalURL)
		# New
		self.parent.preferences.remove('JSONPublisher(%s)' % self.canonicalURL)

		publishers = self.parent.preferences.get('JSONPublishers')
		publishers.remove(self.canonicalURL)
		self.parent.preferences.set('JSONPublishers', publishers)
		self.parent.preferences.set('currentPublisher', '')

		self.parent._publishers = {}

class APIFont(object):
	def __init__(self, parent, twObject = None):
		self.parent = parent
		self.twObject = twObject

		# Init attributes
		self.keywords = ['beta', 'free', 'licenseAllowanceDescription', 'licenseKeyword', 'name', 'postScriptName', 'previewImage', 'purpose', 'requiresUserID', 'seatsAllowedForUser', 'seatsInstalledByUser', 'timeAddedForUser', 'timeFirstPublished', 'format', 'uniqueID', 'upgradeLicenseURL', 'variableFont', 'setName', 'versions']
		for keyword in self.keywords:
			setattr(self, keyword, None)

		# Take data from twObject
		if self.twObject:
			for keyword in self.keywords:
				setattr(self, keyword, getattr(self.twObject, keyword))

			self.getSortedVersions = self.twObject.getSortedVersions

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


	def fonts(self):

		fonts = []

		for font in self.twObject.fonts:
			newFont = APIFont(self, font)
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

		# Init attributes
		self.keywords = ['backgroundColor', 'description', 'email', 'facebook', 'instagram', 'logo', 'name', 'skype', 'supportEmail', 'telephone', 'twitter', 'website']
		for keyword in self.keywords:
			setattr(self, keyword, None)

		# Take data from twObject
		if self.twObject:
			for keyword in self.keywords:
				setattr(self, keyword, getattr(self.twObject, keyword))


	def families(self):

		families = []
		for family in self.twObject.families:
			newFamily = APIFamily(self, family)
			families.append(newFamily)

		return families


class APISubscription(object):
	u"""\
	Represents an API endpoint, identified and grouped by the canonical URL attribute of the API responses. This API endpoint class can then hold several repositories.
	"""

	def __init__(self, parent, url):
		self.parent = parent
		self.url = url
		self.exists = False

		self.versions = []
		if self.get('versions'):
			for dictData in self.get('versions'):
				api = APIRoot()
				api.parent = self
				api.loadJSON(dictData)
				self.versions.append(api)

	def resourceByURL(self, url, binary = False):
		u'''Caches and returns content of a HTTP resource. If binary is set to True, content will be stored and return as a bas64-encoded string'''

		# Save resource
		resourcesList = self.get('resources') or []
		if not url in resourcesList:
			resourcesList.append(url)
			self.set('resources', resourcesList)

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

	def foundries(self):
		foundries = []

		for foundry in self.latestVersion().response.getCommand().foundries:

			newFoundry = APIFoundry(self, twObject = foundry)

			foundries.append(newFoundry)

		return foundries


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

		api = self.latestVersion()

		# Get font
		for foundry in self.foundries():
			for family in foundry.families():
				for font in family.fonts():
					if font.uniqueID == fontID:

						if font.requiresUserID:
						
							# Build URL
							url = self.url
							url = self.parent.parent.addAttributeToURL(url, 'command', 'uninstallFont')
							url = self.parent.parent.addAttributeToURL(url, 'fontID', urllib.quote_plus(fontID))
							url = self.parent.parent.addAttributeToURL(url, 'anonymousAppID', self.parent.parent.anonymousAppID())

							print 'Uninstalling %s in %s' % (fontID, folder)
							print url

							acceptableMimeTypes = UNINSTALLFONTCOMMAND['acceptableMimeTypes']

							try:
								response = urllib2.urlopen(url)

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

		api = self.latestVersions()


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
							response = urllib2.urlopen(url)

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


		return False, 'No font was found to install.'

	def latestVersion(self):
		if self.versions:
			return self.versions[-1]

	def update(self):
		api, responses = self.parent.parent.readResponse(self.url, INSTALLABLEFONTSCOMMAND['acceptableMimeTypes'])
		if responses['errors']:
			return False, '\n'.join(responses['errors'])
		self.addVersion(api)
		return True, None


	def get(self, key):
		preferences = dict(self.parent.parent.preferences.get(self.url) or self.parent.parent.preferences.get('JSONSubscription(%s)' % self.url) or {})
		if preferences.has_key(key):

			o = preferences[key]

			if 'Array' in o.__class__.__name__:
				o = list(o)

			elif 'Dictionary' in o.__class__.__name__:
				o = dict(o)

			return o

	def set(self, key, value):
		preferences = dict(self.parent.parent.preferences.get(self.url) or self.parent.parent.preferences.get('JSONSubscription(%s)' % self.url) or {})
		preferences[key] = value
		self.parent.parent.preferences.set('JSONSubscription(%s)' % self.url, preferences)

	def save(self):
		subscriptions = self.parent.get('subscriptions') or []
		if not self.url in subscriptions:
			subscriptions.append(self.url)
		self.parent.set('subscriptions', subscriptions)

		self.set('versions', [x.dumpJSON() for x in self.versions])

	def addVersion(self, api):
		if self.versions:
			self.versions[-1] = api
		else:
			self.versions = [api]

		self.save()

	def delete(self, calledFromParent = False):

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
		self.parent.parent.preferences.remove('JSONSubscription(%s)' % self.url)

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

	import inspect
	classNames = []
	for name, cls in inspect.getmembers(sys.modules[__name__], inspect.isclass):
		print inspect.getmro(cls)

	client = APIClient(preferences = AppKitNSUserDefaults('world.type.clientapp'))

	print client.addSubscription('https://typeworldserver.com/api/toy6FQGX6c368JlntbxR/?command=installableFonts')

# 	for endpoint in client.publishers():
# 		print endpoint
# 		for subscription in endpoint.subscriptions():
# 			print subscription.latestVersion()
# #			subscription.update()
