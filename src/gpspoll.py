import gps
import threading
import time
import sys
import math
import dateutil.parser
import datetime
from datetime import timedelta, tzinfo

ZERO = timedelta(0)

# A UTC class.
class UTC(tzinfo):
    """UTC"""

    def utcoffset(self, dt):
        return ZERO

    def tzname(self, dt):
        return "UTC"

    def dst(self, dt):
        return ZERO

utc = UTC()

def dist_to_str (f):
	return "{:.0f}/10".format (f * 10)

def deg_to_str (f):

	f=math.fabs(f)

	deg_mod = math.modf(f);
	fdeg = deg_mod[1]
	fmin = deg_mod[0]
	min_mod = math.modf(fmin * 60)
	fmin = min_mod[1]
	fsec = min_mod[0] * 60
    
	return "{:03.0f}/1,{:02.0f}/1,{:05.0f}/1000".format(fdeg, fmin, fsec*1000)

class gpspoll (threading.Thread):
	def __init__(self):
		threading.Thread.__init__(self)
		print "gpspoll:init - starting"
		self.session = gps.gps("localhost", "2947")
		self.session.stream(gps.WATCH_ENABLE | gps.WATCH_NEWSTYLE)
		self.running = True
		print "gpspoll:init - done"

	def run(self):
		while(self.running):
			sys.stdout.flush()
			self.session.next()

	def stop(self):
		print "gpspoll:stop - waiting for polling thread to finish"
		self.running = False
		self.join()
		print "gpspoll:stop - polling thread finished"

	def get(self, max_age = None):
		if not(self.session.utc):
			print "gpspoll:get - no gps"
			return None
	
		if max_age:
			age = time.time() - (dateutil.parser.parse(self.session.utc) - datetime.datetime(1970,1,1,0,0,0,0, UTC())).total_seconds()
			if (max_age < age):
				print "gpspoll:get - gps too old ({:.2f}s old)".format(age)
				return None
		
		#print "gpspoll:get - gps ok ({:.2f}s old)".format(time.time() - (dateutil.parser.parse(self.session.utc) - datetime.datetime(1970,1,1,0,0,0,0, UTC())).total_seconds())
		return self.session.fix
