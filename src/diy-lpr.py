# main script to launch the lpr

import traceback
import threading
import random
import sys

import camcap
import recognizer

import time

PROJECT_DIR = "/home/jascha/projects/diy-lpr/work"

CAPTURE_DIR = PROJECT_DIR + "/capture"
CAPTURE_CTL_FILE = PROJECT_DIR + "/capture_ctl" # if specified, only capture when this file is present

MAX_FILES = 10000

POSTPROC_HIT_DIR = PROJECT_DIR  + "/proc-hit" # where to put files w/ hit after processing
POSTPROC_LOWCONF_DIR = PROJECT_DIR  + "/proc-lowconf" # where to put files w/ low confidence after processing
#POSTPROC_NOHIT_DIR = PROJECT_DIR  + "/work/proc-nohit" # where to put files w/ no hit after processing
POSTPROC_NOHIT_DIR = None # where to put files w/ no hit after processing - None deletes the files

OUTPUT_JSON = PROJECT_DIR  + "/output/json"
OUTPUT_CSV = PROJECT_DIR  + "/output/output.csv"

DEFAULT_REGION = "ma"
MIN_CONF_PATTERNMATCH = 75.0
MIN_CONF_NOPATTERNMATCH = 85.0

RECOGNIZER_THREADS = 3 # we have four processor cores

try:
    print "diy-lpr - setting up camcap"
    cam = camcap.camcap()
    
    cam.camera_port = camcap.PORT_VIDEO
    cam.resolution = camcap.RESOLUTION_LOW
    cam.camera_hflip = True
    cam.camera_vflip = True
    cam.iso = 800
    cam.exposure_mode = 'sports'

    print "diy-lpr - done setting up camcap"

    print "diy-lpr - setting up {} recognizer objects".format(RECOGNIZER_THREADS)
    recogs = []
    lock = threading.RLock();
    

    for x in range(RECOGNIZER_THREADS):
        recog = recognizer.recognizer (
            source_dir = CAPTURE_DIR,
            postproc_hit_dir = POSTPROC_HIT_DIR,
            postproc_nohit_lowconf_dir = POSTPROC_LOWCONF_DIR,
            postproc_nohit_dir = POSTPROC_NOHIT_DIR,
            output_json_dir= OUTPUT_JSON,
            output_csv_file = OUTPUT_CSV,
            default_region=DEFAULT_REGION,
            lock = lock
        )

        recog.min_conf_patternmatch = MIN_CONF_PATTERNMATCH
        recog.min_conf_nopatternmatch = MIN_CONF_NOPATTERNMATCH
        
        recogs.append(recog)

    print "diy-lpr - done setting up recognizers"


    print "diy-lpr - starting camcap auto capture"
    cam.start_auto_capture(target_dir = CAPTURE_DIR, sleep_secs = .01, max_files = MAX_FILES, ctl_file = CAPTURE_CTL_FILE)

    print "diy-lpr - starting {} recognizer threads".format(len(recogs))
    for recog in recogs:
        recog.start()
        time.sleep(random.random() * 5) # sleep a bit so the threads are offset from each other

    # loop forever while th threads do their thing
    while True:
        sys.stdout.flush()
        time.sleep (0.1)

except KeyError:
	pass
except (KeyboardInterrupt, SystemExit):
	pass
except:
    traceback.print_exc()
    pass

print "diy-lpr stopping"
cam.stop()
for recog in recogs:
    recog.stop()
