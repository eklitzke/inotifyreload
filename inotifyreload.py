import os
import sys
import time
import threading
import pwd

import pyinotify

class ReloadThread(threading.Thread):

	def __init__(self, prefix, req, interval=1.0):
		threading.Thread.__init__(self)
		self.prefix = prefix
		self.interval = interval
		self.known_files = set()

		def kill_self(fname):
			if fname in self.known_files:
				req.child_terminate()
	
		wm = pyinotify.WatchManager()
		self.notifier = pyinotify.ThreadedNotifier(wm, kill_self)

	def update_known_files(self):
		"""Update self.known_files"""
		def canonicalize_filename(filename):
			if filename.endswith('.pyc') or filename.endswith('.pyo'):
				return filename[:-1]
			return filename

		loaded_files = (getattr(x, '__file__', None) for x in sys.modules.values())
		loaded_files = (x for x in loaded_files if x and x.startswith(self.prefix))
		self.known_files = set(canonicalize_filename(x) for x in loaded_files)
	
	def run(self):
		self.notifier.start()

		mask = (pyinotify.IN_CREATE |
				pyinotify.IN_DELETE |
				pyinotify.IN_MODIFY )

		self.update_known_files()
		wm.add_watch(prefix, mask, rec=True)

		while True:
			time.sleep(self.interval)
			self.update_known_files()

def yelp_run_reloader(req):
	username = pwd.getpwuid(os.getuid()).pw_name
	pgname = '/nail/pg/%s' % username
	reload_thread = ReloadThread(prefix=pgname, req=req)
	reload_thread.start()
