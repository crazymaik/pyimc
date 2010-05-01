#!/usr/bin/python

import sys
import subprocess
import dbus
import os
import ConfigParser

class SkypeWrapper(object):
	def __init__(self, bus):
		try:
			self.proxy = bus.get_object('com.Skype.API', '/com/Skype')
			self.proxy.Invoke('NAME imcontrol')
			self.proxy.Invoke('PROTOCOL 8')
		except dbus.DBusException:
			self.proxy = None

	def lookup_friends(self):
		if self.proxy == None:
			return {}
		self.friends = {}
		accounts = {'skype': []}
		for friend in self.search_friends():
			name = self.get_name(friend)
			accounts['skype'].append({'name': name, 'on': self.is_online(friend)})
			self.friends[name] = friend
		return accounts

	def open_chat(self, name):
		friend = self.friends[name]
		res = self.proxy.Invoke('CHAT CREATE ' + friend)
		self.proxy.Invoke('OPEN CHAT ' + res.split()[1])

	def search_friends(self):
		res = self.proxy.Invoke('SEARCH FRIENDS')
		res = res.split(', ')
		res[0] = res[0].split()[1]
		return res

	def get_name(self, friend):
		res = self.proxy.Invoke('GET USER %s DISPLAYNAME' % friend)
		res = res.split()
		if len(res) == 3:
			res = self.proxy.Invoke('GET USER %s FULLNAME' % friend)
			res = res.split()
		if len(res) == 3:
			res += [friend]
		return ' '.join(res[3:])

	def is_online(self, friend):
		return self.proxy.Invoke('GET USER %s ONLINESTATUS' % friend).split()[3] != 'OFFLINE'

class PidginWrapper(object):
	def __init__(self, bus):
		try:
			obj = bus.get_object('im.pidgin.purple.PurpleService',
			                     '/im/pidgin/purple/PurpleObject')
			self.proxy = dbus.Interface(obj, 'im.pidgin.purple.PurpleInterface')
		except dbus.DBusException as e:
			self.proxy = None

	def lookup_friends(self):
		if self.proxy == None:
			return {}
		accounts = {}
		self.friends = {}
		self.accounts = {}
		for account in self.proxy.PurpleAccountsGetAllActive():
			proto = self.proxy.PurpleAccountGetProtocolName(account).lower()
			self.accounts[proto] = account
			self.friends[proto] = {}
			accounts[proto] = []
			for friend in self.proxy.PurpleFindBuddies(account, ''):
				name = self.proxy.PurpleBuddyGetAlias(friend)
				accounts[proto].append({'name': name, 'on': self.is_online(friend)})
				self.friends[proto][name] = friend
		return accounts

	def open_chat(self, proto, name):
		_name = self.proxy.PurpleBuddyGetName(self.friends[proto][name])
		conv = self.proxy.PurpleConversationNew(1, self.accounts[proto], _name)
		self.proxy.PurpleConverstationPresent(conv)

	def is_online(self, friend):
		return self.proxy.PurpleBuddyIsOnline(friend)

class Config(object):
	"""	
	A object to wrap a dictionary for easier configuration access.
	
	Based on Storage in web.py (public domain)
	"""	
	def __init__(self):
		self._config = {
			# general options
			'skype': '1',
			'pidgin': '1',
			# horicontal options
			'incase': '1',
			'xmms': '1',
			'bottom': '0',
			'x': '680',
			'y': '200',
			'w': '240',
			'fn': '\"-*-verdana-medium-r-*-*-16-*-*-*-*-*-iso10646-1\"',
			'nb': '#000000',
			'nf': '#9999CC',
			'sb': '#000066',
			'sf': '#FFFFFF',
			# vertically options
			'resize': '1'}
		config_file = os.path.expanduser('~/.controlimrc')
		if os.path.lexists(config_file):
			try:
				parser = ConfigParser.SafeConfigParser()
				f = open(config_file)
				parser.readfp(f)
				config.get_dict().update(dict(parser.items('DEFAULT', raw=True)))
			except (IOError, ConfigParser.ParsingError), e:
				print >> sys.stderr, "Configuration file can not be read %s\n%s" % (config_file, e)
				sys.exit(1)

	def get_config(self):
		''' Get the contained configuration.'''
		return self._config
	
	def __getattr__(self, key):
		try:
			return self._config[key]
		except KeyError, k:
			raise AttributeError, k 
		
	def __setattr__(self, key, value):
		if key == '_config':
			object.__setattr__(self, key, value)
		else:
			self._config[key] = value
			
	def __delattr__(self, key):
		try:
			del self._config[key]
		except KeyError, k:
			raise AttributeError, k 

	# For container methods pass-through to the underlying config.
	def __getitem__(self, key):
		return self._config[key] 
	
	def __setitem__(self, key, value):
		self._config[key] = value 
		
	def __delitem__(self, key):
		del self._config[key] 
		
	def __repr__(self):
		return '<Storage ' + repr(self._config) + '>'

def main():
	config = Config()
	
	bus = dbus.SessionBus()
	pidgin = PidginWrapper(bus)
	skype = SkypeWrapper(bus)

	coll = skype.lookup_friends()
	coll.update(pidgin.lookup_friends())

	dmenu = ["dmenu","-i","-l","10","-rs","-ni","-xs","-x","680","-y","200","-w","240"
	        ,"-fn", "\"-*-verdana-medium-r-*-*-16-*-*-*-*-*-iso10646-1\""]
	p = subprocess.Popen(dmenu, stdin=subprocess.PIPE, stdout=subprocess.PIPE)

	for proto, friends in coll.iteritems():
		for friend in friends:
			out = '%s on %s\n' % (friend['name'], proto.upper() if friend['on'] else proto)
			outencoded = out.encode("ascii", "replace")
			p.stdin.write(outencoded)

	wanted = p.communicate()[0]
	if wanted == "":
		return 0

	proto = wanted.split()[-1].lower()
	name = wanted[:wanted.rfind(' on ')]

	if proto == 'skype':
		skype.open_chat(name)
	else:
		pidgin.open_chat(proto, name)

	return 0

if __name__ == '__main__':
	sys.exit(main())

