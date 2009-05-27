import os
import signal
import threading
import select

import pyinotify

def default_rule(pathname):
	"""The default rule tries to detect changes made to Python files in an
	intelligent way (e.g. ignores temp files created by Emacs).
	"""
	base = os.path.basename(pathname)

	# Emacs cruft
	if base.startswith('.#'):
		return False

	return base.endswith('.py')

class ReloadThread(threading.Thread):
	"""Bump Apache when .py files change; uses inotify for efficiency.

	This thread sets up an inotify handler on a specified directory. Whenver
	files in this directory change, the filename is passed into a list of
	rules. If any of those rules matches (i.e. returns True), an arbitrary
	action is executed.

	The default behavior is to watch for changes to .py files, and set SIGUSR1
	to the current PID when that happens. This has the effect of causing Apache
	to do a `graceful' restart.
	"""

	def __init__(self, prefix):
		threading.Thread.__init__(self)
		self.prefix = os.path.realpath(prefix)
		self.rules = []

		def do_action(inotify_obj):
			filepath = inotify_obj.pathname
			if any(rule(filepath) for rule in self.list_rules()):
				self.action(filepath)

		self.wm = pyinotify.WatchManager()
		self.notifier = pyinotify.ThreadedNotifier(self.wm, do_action)

	def list_rules(self):
		return self.rules or [default_rule]

	def add_rule(self, func):
		"""Add a rule to the current object. A rule should be a function that
		takes a single argument, a path to a file, and returns True if
		self.action should be executed and false otherwise.
		"""
		self.rules.append(func)

	def action(self, filename):
		"""This action is run when a rule is matched. The argument passed in is
		the filename of the file that matched a rule.

		The default action is to send SIGUSR1 to the current process, which
		gracefuls an Apache. Just subclass this class and override this method
		if you want to change it.
		"""
		os.kill(os.getpid(), signal.SIGUSR1)

	def run(self):
		self.notifier.start()

		mask = (pyinotify.IN_CREATE |
				pyinotify.IN_DELETE |
				pyinotify.IN_MODIFY )

		self.wm.add_watch(self.prefix, mask, rec=True)

		# Force this thread to sleep forever
		select.select([], [], [])

__all__ = ['ReloadThread']
