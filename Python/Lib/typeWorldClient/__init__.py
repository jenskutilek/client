# -*- coding: utf-8 -*-

import datetime
import os, sys, json, platform, urllib.request, urllib.parse, urllib.error, urllib.request, urllib.error, urllib.parse, re, traceback, json, time, base64, certifi


import typeWorld.api, typeWorld.api.base
from typeWorld.api import *
from typeWorld.api.base import *

from ynlib.files import ReadFromFile, WriteToFile
from ynlib.system import Execute


import platform
WIN = platform.system() == 'Windows'
MAC = platform.system() == 'Darwin'




def readJSONResponse(url, acceptableMimeTypes, data = {}):
	d = {}
	d['errors'] = []
	d['warnings'] = []
	d['information'] = []

	# Take URL apart here
	customProtocol, transportProtocol, subscriptionID, secretKey, restDomain = splitJSONURL(url)
	url = transportProtocol + restDomain

	# Validate
	api = typeWorld.api.APIRoot()

	try:
		request = urllib.request.Request(url)

		data = urllib.parse.urlencode(data)
		data = data.encode('ascii')
		
		print ('readJSONResponse():', url, data)

		response = urllib.request.urlopen(request, data, cafile=certifi.where())


		if response.getcode() != 200:
			d['errors'].append('Resource returned with HTTP code %s' % response.code)

		if not response.headers['content-type'] in acceptableMimeTypes:
			d['errors'].append('Resource headers returned wrong MIME type: "%s". Expected is %s.' % (response.headers['content-type'], acceptableMimeTypes))

		if response.getcode() == 200:

			api.loadJSON(response.read().decode())

			information, warnings, errors = api.validate()

			if information:
				d['information'].extend(information)
			if warnings:
				d['warnings'].extend(warnings)
			if errors:
				d['errors'].extend(errors)

	except:
		d['errors'].append(traceback.format_exc())

	return api, d



def addJSONSubscription(url):


	responses = {
		'information': [],
		'warnings': [],
		'errors': [],
	}

	data = {}


	if url.count('@') > 1:
		responses['errors'].append('URL contains more than one @ sign, so don’t know how to parse it.')
		return responses, None

	if not '://' in url:
		responses['errors'].append('URL is malformed.')
		return responses, None


	if url.split('://')[1].count(':') > 2:
		responses['errors'].append('URL contains more than one : sign, so don’t know how to parse it.')
		return responses, None

	customProtocol, transportProtocol, subscriptionID, secretKey, restDomain = splitJSONURL(url)

	if not transportProtocol:
		responses['errors'].append('No transport protocol defined (http:// or https://).')
		return responses, None

	# Both subscriptionID as well as secretKey defined
	if subscriptionID and secretKey:
		url = transportProtocol + subscriptionID + ':' + 'secretKey' + '@' + restDomain
	elif subscriptionID and not secretKey:
		url = transportProtocol + subscriptionID + '@' + restDomain
	else:
		url = transportProtocol + restDomain

	# Read response
	api, responses = readJSONResponse(url, typeWorld.api.base.INSTALLABLEFONTSCOMMAND['acceptableMimeTypes'], data = {'subscriptionID': subscriptionID, 'secretKey': secretKey})

	# Errors
	if responses['errors']:
		return responses, None

	# Check for installableFonts response support
	if not 'installableFonts' in api.supportedCommands and not 'installFonts' in api.supportedCommands:
		responses['errors'].append('API endpoint %s does not support the "installableFonts" and "installFonts" commands.' % api.canonicalURL)
		return responses, None

	# Read response again, this time with installableFonts command
	api, responses = readJSONResponse(url, typeWorld.api.base.INSTALLABLEFONTSCOMMAND['acceptableMimeTypes'], data = {'subscriptionID': subscriptionID, 'secretKey': secretKey, 'command': 'installableFonts'})

	# Errors
	if responses['errors']:
		return responses, None

	if not api.response:
		responses['errors'].append('API response has only root, no response attribute attached. Expected: installableFonts response.')
		return responses, None

	if api.response.getCommand().type == 'error':
		responses['errors'].append(api.response.getCommand().errorMessage)
		return responses, None

	# Success
	data['subscriptionID'] = subscriptionID
	data['secretKey'] = secretKey
	return responses, api, data



def splitJSONURL(url):

	customProtocol = 'typeworldjson://'
	url = url.replace(customProtocol, '')

	url = url.replace('http//', 'http://')
	url = url.replace('https//', 'https://')
	url = url.replace('HTTP//', 'http://')
	url = url.replace('HTTPS//', 'https://')


	transportProtocol = None
	if url.lower().startswith('https://'):
		transportProtocol = 'https://'
	elif url.lower().startswith('http://'):
		transportProtocol = 'http://'

	urlRest = url[len(transportProtocol):]

	subscriptionID = ''
	secretKey = ''
	if '@' in urlRest:

		credentials, restDomain = urlRest.split('@')

		# Both subscriptionID as well as secretKey defined
		if ':' in credentials:
			subscriptionID, secretKey = credentials.split(':')
			keyURL = transportProtocol + subscriptionID + ':' + 'secretKey' + '@' + restDomain
		else:
			subscriptionID = credentials
			secretKey = None
			keyURL = transportProtocol + subscriptionID + '@' + restDomain

		actualURL = transportProtocol + restDomain

	# No credentials given
	else:
		keyURL = url
		actualURL = url
		restDomain = urlRest

	return customProtocol, transportProtocol, subscriptionID, secretKey, restDomain


class Preferences(object):
	pass

class JSON(Preferences):
	def __init__(self, path):
		self.path = path
		self._dict = {}


		if self.path and os.path.exists(self.path):
			self._dict = json.loads(ReadFromFile(self.path))

	def get(self, key):
		if key in self._dict:
			return self._dict[key]

	def set(self, key, value):
		self._dict[key] = value
		self.save()

	def remove(self, key):
		if key in self._dict:
			del self._dict[key]

	def save(self):

		if not os.path.exists(os.path.dirname(self.path)):
			os.makedirs(os.path.dirname(self.path))
		WriteToFile(self.path, json.dumps(self._dict))

	def dictionary(self):
		return self._dict


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
				o = str(o)


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
	"""\
	Main Type.World client app object. Use it to load repositories and install/uninstall fonts.
	"""

	def __init__(self, preferences = None):
		self.preferences = preferences
		self._publishers = {}
		self._subscriptionsUpdated = []


	def keyring(self):

		import keyring

		if MAC:
			from keyring.backends.OS_X import Keyring
			keyring.core.set_keyring(keyring.core.load_keyring('keyring.backends.OS_X.Keyring'))
		if WIN:
			from keyring.backends.Windows import WinVaultKeyring
			keyring.core.set_keyring(keyring.core.load_keyring('keyring.backends.Windows.WinVaultKeyring'))

		return keyring


	def log(self, message):
		if WIN:
			from AppKit import NSLog
			NSLog('Type.World Client: %s' % message)

	def prepareUpdate(self):

		self._subscriptionsUpdated = []

	def allSubscriptionsUpdated(self):

		numSubscriptions = 0
		for publisher in self.publishers():
			numSubscriptions += len(publisher.subscriptions())

		if len(self._subscriptionsUpdated) == numSubscriptions:
			return True



	def resourceByURL(self, url, binary = False, update = False, username = None, password = None):
		'''Caches and returns content of a HTTP resource. If binary is set to True, content will be stored and return as a bas64-encoded string'''

		resources = self.preferences.get('resources') or {}

		if url not in resources or update:

			print('resourceByURL', url)

			request = urllib.request.Request(url)
			if username and password:
				base64string = base64.b64encode(b"%s:%s" % (username, password)).decode("ascii")
				request.add_header("Authorization", "Basic %s" % base64string)   
				print('with username and password %s:%s' % (username, password))
			response = urllib.request.urlopen(request, cafile=certifi.where())


			if response.getcode() != 200:
				return False, 'Resource returned with HTTP code %s' % response.code

			else:
				content = response.read()
				if binary:
					content = base64.b64encode(content).decode()
				else:
					content = content.decode()

				resources[url] = response.headers['content-type'] + ',' + content
				self.preferences.set('resources', resources)

				return True, content, response.headers['content-type']

		else:

			response = resources[url]
			mimeType = response.split(',')[0]
			content = response[len(mimeType)+1:]

			return True, content, mimeType




	def readGitHubResponse(self, url, username = None, password = None):

		d = {}
		d['errors'] = []
		d['warnings'] = []
		d['information'] = []

		json = ''

		try:

			print('readGitHubResponse(%s)' % url)

			request = urllib.request.Request(url)
			if username and password:
				base64string = base64.b64encode(b"%s:%s" % (username, password)).decode("ascii")
				request.add_header("Authorization", "Basic %s" % base64string)   
			response = urllib.request.urlopen(request, cafile=certifi.where())

			if response.getcode() == 404:
				d['errors'].append('Server returned with error 404 (Not found).')
				return None, d

			if response.getcode() == 401:
				d['errors'].append('User authentication failed. Please review your username and password.')
				return None, d

			if response.getcode() != 200:
				d['errors'].append('Resource returned with HTTP code %s' % response.code)

			# if not response.headers['content-type'] in acceptableMimeTypes:
			# 	d['errors'].append('Resource headers returned wrong MIME type: "%s". Expected is %s.' % (response.headers['content-type'], acceptableMimeTypes))
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

		try:

			if url.startswith('typeworldjson://'):

				print('client.addSubscription()')


				responses, api, data = addJSONSubscription(url)

				if not responses['errors']:

					publisher = self.publisher(api.canonicalURL)
					publisher.set('type', 'JSON')
					success, message = publisher.addJSONSubscription(url, api, subscriptionID = data['subscriptionID'], secretKey = data['secretKey'])
					publisher.save()
					publisher.stillAlive()
					return success, message, self.publisher(api.canonicalURL)

				else:

					return False, responses['errors'][0], None


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

		except:

			exc_type, exc_value, exc_traceback = sys.exc_info()
			return False, traceback.format_exc(), None


	def publisher(self, canonicalURL):
		if canonicalURL not in self._publishers:
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
	"""\
	Represents an API endpoint, identified and grouped by the canonical URL attribute of the API responses. This API endpoint class can then hold several repositories.
	"""

	def __init__(self, parent, canonicalURL):
		self.parent = parent
		self.canonicalURL = canonicalURL
		self.exists = False
		self._subscriptions = {}

		self._updatingSubscriptions = []

	def stillUpdating(self):
		return len(self._updatingSubscriptions) > 0


	def updatingProblem(self):

		problems = []

		for subscription in self.subscriptions():
			problem = subscription.updatingProblem()
			if problem and not problem in problems:
				problems.append(problem)

		if problems:
			return problems


	def stillAlive(self):

		# Register endpoint
		url = 'https://type.world/registerAPIEndpoint/?url=%s' % urllib.parse.quote(self.canonicalURL)
		request = urllib.request.Request(url)
		try:
			response = urllib.request.urlopen(request, cafile=certifi.where())
		except urllib.error.HTTPError as e:
			print('API endpoint alive HTTP error: %s' % e)
			return
		response = json.loads(response.read())

		if response['success'] == True:
			print('API endpoint alive success.')
		else:
			print('API endpoint alive error: %s' % response['message'])


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
		keyring = self.parent.keyring()
		return keyring.get_password("Type.World GitHub Subscription %s (%s)" % (self.canonicalURL, username), username)

	def setPassword(self, username, password):
		keyring = self.parent.keyring()
		keyring.set_password("Type.World GitHub Subscription %s (%s)" % (self.canonicalURL, username), username, password)

	def resourceByURL(self, url, binary = False, update = False):
		'''Caches and returns content of a HTTP resource. If binary is set to True, content will be stored and return as a bas64-encoded string'''

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
		return len(self.installedFonts())

	def installedFonts(self):
		l = []

		for subscription in self.subscriptions():
			for font in subscription.installedFonts():
				if not font in l:
					l.append(font)

		return l

	def amountOutdatedFonts(self):
		return len(self.outdatedFonts())

	def outdatedFonts(self):
		l = []

		for subscription in self.subscriptions():
			for font in subscription.outdatedFonts():
				if not font in l:
					l.append(font)

		return l

	def currentSubscription(self):
		if self.get('currentSubscription'):
			subscription = self.subscription(self.get('currentSubscription'))
			if subscription:
				return subscription
			else:
				return self.subscriptions()[0]

	def get(self, key):
		preferences = dict(self.parent.preferences.get(self.canonicalURL) or self.parent.preferences.get('publisher(%s)' % self.canonicalURL) or {})
		if key in preferences:

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

	def addJSONSubscription(self, url, api, subscriptionID = None, secretKey = None):

		self.parent._subscriptions = {}

		subscription = self.subscription(url)


		subscription.addJSONVersion(api)
		self.set('currentSubscription', url)
		subscription.save()

		if secretKey:
			subscription.setSecretKey(secretKey)

		return True, None

	def addGitHubSubscription(self, url, commits):

		self.parent._subscriptions = {}

		subscription = self.subscription(url)
		subscription.set('commits', commits)
		self.set('currentSubscription', url)
		subscription.save()

		return True, None


	def subscription(self, url):
		if url not in self._subscriptions:
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
			if url in resources:
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
		self.keywords = self.twObject.nonListProxyBasedKeys()
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


	def isOutdated(self):

		installedVersion = self.installedVersion()
		return installedVersion and installedVersion != self.getVersions()[-1].number


	def installedVersion(self, folder = None):
		for version in self.getVersions():
			if os.path.exists(self.path(version.number, folder)):
				return version.number




	def delete(self):
		self.parent.parent.parent.removeFont(self.uniqueID)


	def getVersions(self):
		if self.twObject:
			return self.twObject.getVersions()

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

		if WIN:
			return os.path.join(os.environ['WINDIR'], 'Fonts', self.filename(version))

		if MAC:

			# User fonts folder
			if not folder:
				folder = self.parent.parent.parent.parent.path()
				
			return os.path.join(folder, self.filename(version))


class APIFamily(object):
	def __init__(self, parent, twObject = None):
		self.parent = parent
		self.twObject = twObject

		# Init attributes
		self.keywords = self.twObject.nonListProxyBasedKeys()
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

			print('gitHubFonts()')

			url = self.parent.parent.url
			owner = url.split('/')[3]
			repo = url.split('/')[4]
			path = '/'.join(url.split('/')[5:]) + '/fonts'

			print(url)

			
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
	"""\
	Represents an API endpoint, identified and grouped by the canonical URL attribute of the API responses. This API endpoint class can then hold several repositories.
	"""

	def __init__(self, parent, url):
		self.parent = parent
		self.url = url
		self.exists = False

		self._updatingProblem = None

		print('<API SUbscription %s>' % self.url)

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
			return self.latestVersion().response.getCommand().name.getText(locale) or '#(Unnamed)'
		if self.parent.get('type') == 'GitHub':
			return self.url.split('/')[-1]


	def resourceByURL(self, url, binary = False, update = False):
		'''Caches and returns content of a HTTP resource. If binary is set to True, content will be stored and return as a bas64-encoded string'''

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
		if url not in self._subscriptions:
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
		return len(self.installedFonts())

	def installedFonts(self):
		l = []
		# Get font
		for foundry in self.foundries():
			for family in foundry.families():
				for font in family.fonts():
					if font.installedVersion():
						if not font in l:
							l.append(font.uniqueID)
		return l

	def amountOutdatedFonts(self):
		return len(self.outdatedFonts())

	def outdatedFonts(self):
		l = []
		# Get font
		for foundry in self.foundries():
			for family in foundry.families():
				for font in family.fonts():
					installedFontVersion = font.installedVersion()
					if installedFontVersion and installedFontVersion != font.getVersions()[-1].number:
						if not font in l:
							l.append(font.uniqueID)
		return l

	def installedFontVersion(self, fontID = None, folder = None):

		for foundry in self.foundries():
			for family in foundry.families():
				for font in family.fonts():
					if font.uniqueID == fontID:
						return font.installedVersion()

	def removeFont(self, fontID, folder = None):


		# Get font
		for foundry in self.foundries():
			for family in foundry.families():
				for font in family.fonts():
					if font.uniqueID == fontID:

						# TODO: remove this for final version
						if (hasattr(font, 'requiresUserID') and font.requiresUserID) or (hasattr(font, 'protected') and font.protected):
						
							try:
								customProtocol, transportProtocol, subscriptionID, secretKey, restDomain = splitJSONURL(self.url)
								url = transportProtocol + restDomain

								data = {
									'command': 'uninstallFont',
									'fontID': urllib.parse.quote_plus(fontID),
									'anonymousAppID': self.parent.parent.anonymousAppID(),
									'subscriptionID': self.subscriptionID(),
									'secretKey': self.getSecretKey(),
								}

								print('curl -d "%s" -X POST %s' % ('&'.join(['{0}={1}'.format(k, v) for k,v in data.items()]), url))

								api, messages = readJSONResponse(url, UNINSTALLFONTCOMMAND['acceptableMimeTypes'], data = data)

								if messages['errors']:
									return False, '\n\n'.join(messages['errors'])

								if api.response.getCommand().type == 'seatAllowanceReached':
									return False, 'seatAllowanceReached'
								

								# REMOVE
								installedFontVersion = font.installedVersion()

								if installedFontVersion:
									# Delete file
									path = font.path(installedFontVersion, folder)


									if os.path.exists(path):

										try:
											os.remove(path)
										except PermissionError:
											return False, "Insufficient permission to delete font."

								# Ping
								self.parent.stillAlive()

								return True, None


							except:
								exc_type, exc_value, exc_traceback = sys.exc_info()
								return False, traceback.format_exc()

						else:
							# REMOVE
							installedFontVersion = font.installedVersion()

							if installedFontVersion:
								# Delete file

								path = font.path(installedFontVersion, folder)

								if os.path.exists(path):

									try:
										os.remove(path)
									except PermissionError:
										return False, "Insufficient permission to delete font."

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
							try:

								customProtocol, transportProtocol, subscriptionID, secretKey, restDomain = splitJSONURL(self.url)
								url = transportProtocol + restDomain

								data = {
									'command': 'installFont',
									'fontID': urllib.parse.quote_plus(fontID),
									'fontVersion': str(version),
									'anonymousAppID': self.parent.parent.anonymousAppID(),
									'subscriptionID': self.subscriptionID(),
									'secretKey': self.getSecretKey(),
								}

								print('curl -d "%s" -X POST %s' % ('&'.join(['{0}={1}'.format(k, v) for k,v in data.items()]), url))

								api, messages = readJSONResponse(url, INSTALLFONTCOMMAND['acceptableMimeTypes'], data = data)

								if messages['errors']:
									return False, '\n\n'.join(messages['errors'])

								if api.response.getCommand().type == 'error':
									return False, api.response.getCommand().errorMessage
								elif api.response.getCommand().type == 'seatAllowanceReached':
									return False, 'seatAllowanceReached'
								elif api.response.getCommand().type == 'success':
								

									if MAC or WIN:

										# Write file
										path = font.path(version, folder)

										try:
											# Create folder if it doesn't exist
											if not os.path.exists(os.path.dirname(path)):
												os.makedirs(os.path.dirname(path))

											# Put future encoding switches here
											f = open(path, 'wb')
											f.write(base64.b64decode(api.response.getCommand().font))
											f.close()
										except PermissionError:
											return False, "Insufficient permission to install font."

										# Ping
										self.parent.stillAlive()

										if os.path.exists(path):
											return True, None
										else:
											return False, 'Font file could not be written: %s' % path

									else:

										fontPath = font.path(version, folder)

										import tempfile
										tempPath = os.path.join(tempfile.gettempdir(), font.filename(version))

										# Put future encoding switches here
										f = open(tempPath, 'wb')
										f.write(base64.b64decode(api.response.getCommand().font))
										f.close()

										argument_line = '"%s" "%s"' % (tempPath, fontPath)

										print(Execute('runas /user:Administrator "copy %s %s"' % (tempPath, fontPath)))

										# from ctypes import windll
										# ret = windll.shell32.ShellExecuteW(None, u"runas", 'copy', argument_line, None, 1)

										# print ('ret', ret)


										# Ping
										self.parent.stillAlive()


										if os.path.exists(fontPath):
											return True, None
										else:
											return False, 'Font file could not be written: %s' % tempPath

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
										print('Install version %s, commit %s' % (version, commit['sha']))

										owner = self.url.split('/')[3]
										repo = self.url.split('/')[4]
										urlpath = '/'.join(self.url.split('/')[7:]) + '/fonts/' + font.postScriptName + '.' + font.format


										url = 'https://api.github.com/repos/%s/%s/contents/%s?ref=%s' % (owner, repo, urlpath, commit['sha'])
										print(url)
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

	def subscriptionID(self):
		customProtocol, transportProtocol, subscriptionID, secretKey, restDomain = splitJSONURL(self.url)
		return subscriptionID

	def getSecretKey(self):
		subscriptionID = self.subscriptionID()
		keyring = self.parent.parent.keyring()
		return keyring.get_password("Type.World JSON Subscription %s (%s)" % (self.parent.canonicalURL, subscriptionID), subscriptionID)

	def setSecretKey(self, secretKey):
		subscriptionID = self.subscriptionID()
		keyring = self.parent.parent.keyring()
		keyring.set_password("Type.World JSON Subscription %s (%s)" % (self.parent.canonicalURL, subscriptionID), subscriptionID, secretKey)



	def update(self):

		self.parent._updatingSubscriptions.append(self.url)

		# reset
		self._foundries = []

		if self.parent.get('type') == 'JSON':

			data = {'subscriptionID': self.subscriptionID(), 'command': 'installableFonts'}
			secretKey = self.getSecretKey()
			if secretKey:
				data['secretKey'] = secretKey

			api, responses = readJSONResponse(self.url, INSTALLABLEFONTSCOMMAND['acceptableMimeTypes'], data = data)
			if responses['errors']:
				
				self.parent._updatingSubscriptions.remove(self.url)
				self._updatingProblem = '\n'.join(responses['errors'])
				return False, self._updatingProblem

			self.addJSONVersion(api)

			if api.response.getCommand().type == 'error':
				self._updatingProblem = api.response.getCommand().errorMessage
				return False, self._updatingProblem



		elif self.parent.get('type') == 'GitHub':

			owner = self.url.split('/')[3]
			repo = self.url.split('/')[4]
			path = '/'.join(self.url.split('/')[7:])

			commitsURL = 'https://api.github.com/repos/%s/%s/commits?path=%s/fonts' % (owner, repo, path)
			print('commitsURL', commitsURL)

			# Read response
			commits, responses = self.parent.readGitHubResponse(commitsURL)
			self.set('commits', commits)


		self.parent._updatingSubscriptions.remove(self.url)
		self._updatingProblem = None
		self.parent.parent._subscriptionsUpdated.append(self.url)
		return True, None

	def updatingProblem(self):
		return self._updatingProblem

	def get(self, key):
		preferences = dict(self.parent.parent.preferences.get(self.url) or self.parent.parent.preferences.get('subscription(%s)' % self.url) or {})
		if key in preferences:

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

		# Delete all fonts
		for foundry in self.foundries():
			for family in foundry.families():
				for font in family.fonts():
					font.delete()


		# Resources
		resources = self.parent.parent.preferences.get('resources') or {}
		for url in self.get('resources') or []:
			if url in resources:
				print('Deleting resource', url)
				resources.pop(url)
		self.parent.parent.preferences.set('resources', resources)


		# New
		self.parent.parent.preferences.remove('subscription(%s)' % self.url)

		# Subscriptions
		subscriptions = self.parent.get('subscriptions')
		subscriptions.remove(self.url)
		self.parent.set('subscriptions', subscriptions)
		self.parent._subscriptions = {}

		# currentSubscription
		if self.parent.get('currentSubscription') == self.url:
			if len(subscriptions) >= 1:
				self.parent.set('currentSubscription', subscriptions[0])


		if len(subscriptions) == 0 and calledFromParent == False:
			self.parent.delete()

		self.parent._subscriptions = {}


if __name__ == '__main__':

	client = APIClient(preferences = AppKitNSUserDefaults('world.type.clientapp'))

#	print client.addSubscription('typeworldgithub://https://github.com/typeWorld/sampleGithubSubscription/tree/master/fontFamilies/YanoneKaffeesatz')
	print(client.addSubscription('typeworldjson://http://127.0.0.1:5000/?command=installableFonts&userID=5hXmdNNvywkHe2asYLXqJR2T&&anonymousAppID=H625npqamfsy2cnZgNSJWpZm'))

# 	for endpoint in client.publishers():
# 		print endpoint
# 		for subscription in endpoint.subscriptions():
# 			print subscription.latestVersion()
# #			subscription.update()
