import os
import pwd
import signal
import sys
import threading
import time
import types

import pyinotify

def graceful_apache():
	"Sends a graceful signal to Apache"
	log('Sending graceful signal')
	os.kill(os.getpid(), signal.SIGUSR1)

def log(msg):
	import datetime
	msg = '[%s pid=%d] %s\n' % (datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'), os.getpid(), msg)
	f = open('/nail/home/evan/inotify.log', 'a')
	f.write(msg)

class ReloadThread(threading.Thread):
	"""Bump Apache when open .py files change; uses inotify for efficiency.

	This thread sets up an inotify handler on a specified directory. When open,
	used .py files in this directory change, the Apache process is restarted
	gracefully using child_terminate().

	The intention is that the directory to watch should just point to the
	developer's branch. This is to avoid having to watch files in
	/usr/lib/python etc.
	"""

	def __init__(self, prefix, interval=1.0):
		threading.Thread.__init__(self)
		self.prefix = os.path.realpath(prefix)
		self.interval = interval
		self.known_files = set()

		def kill_self(inotify_obj):
			#log('got notification for %s' % inotify_obj)
			pathname = self.canonicalize_filename(inotify_obj.pathname)
			if pathname in self.known_files:
				graceful_apache()

		self.wm = pyinotify.WatchManager()
		self.notifier = pyinotify.ThreadedNotifier(self.wm, kill_self)

		self.setDaemon(True)
		self.daemon = True

	@staticmethod
	def canonicalize_filename(filename):
		if filename.endswith('.pyc') or filename.endswith('.pyo'):
			filename = filename[:-1]
		return os.path.realpath(filename)

	def update_known_files(self):
		"""Update self.known_files

		This figures out what .py files are open by consulting sys.modules, and
		maintains a list of these files in self.known_files.
		"""

		loaded_files = (getattr(x, '__file__', None) for x in sys.modules.values() if type(x) is types.ModuleType)
		loaded_files = (self.canonicalize_filename(x) for x in loaded_files if x is not None)
		loaded_files = (x for x in loaded_files if x.startswith(self.prefix))
		self.known_files = set(loaded_files)

	def run(self):
		self.notifier.start()

		mask = (pyinotify.IN_CREATE |
				pyinotify.IN_DELETE |
				pyinotify.IN_MODIFY )

		self.update_known_files()
		self.wm.add_watch(self.prefix, mask, rec=True)

		# Spin forever, updating the list of known open modules every
		# self.interval seconds
		while True:
			time.sleep(self.interval)
			self.update_known_files()

def start():
	username = pwd.getpwuid(os.getuid()).pw_name
	pgname = os.readlink('/nail/pg/%s/loc' % username)
	reload_thread = ReloadThread(prefix=pgname)
	reload_thread.start()

__all__ = ['ReloadThread', 'start']
