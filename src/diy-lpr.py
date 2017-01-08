# main script to launch the lpr

import traceback
import threading
import random
import sys
import os

import camcap
import recognizer

import time

## BEGIN DIY-ALPR CONFIG

# PROJECT_DIR - the path to the working directory where images and output will be stored
PROJECT_DIR = os.path.dirname(os.path.realpath(__file__)) + "/../work" # assume it is "../work"
# PROJECT_DIR = "/home/USER/diy-alpr/src/work" # you could hard code this

# CAPTURE_DIR - where to store captured images
CAPTURE_DIR = PROJECT_DIR + "/capture" 

# CAPTURE_CTL_FILE (optional) - if specified, images will only be captured when this file 
#                               is present -- allows you to pause/resume  capture
CAPTURE_CTL_FILE = PROJECT_DIR + "/capture_ctl"

# MAX_FILES - max number of files to have in CAPTURE_DIR. capturing will pause until the number of files drops
#             this helps prevent you from running out of disk space if you are capturing images faster than you
#             can recognize them
MAX_FILES = 10000

# POSTPROC_HIT_DIR - where to put files with a license plate hit after recognition
POSTPROC_HIT_DIR = PROJECT_DIR  + "/proc-hit"

# POSTPROC_HIT_LOWCONF_DIR (optional) - where to put files with a low confidence hit after recognition. If None,
#                                       these files will be deleted
POSTPROC_LOWCONF_DIR = PROJECT_DIR  + "/proc-lowconf"

# POSTPROC_NOHIT_DIR (optional) - where to put files with no hit after recognition. If None, these files will be deleted.

POSTPROC_NOHIT_DIR = None
#POSTPROC_NOHIT_DIR = PROJECT_DIR  + "/work/proc-nohit"

# OUTPUT_JSON (optional, if OUTPUT_CSV specified) - on recognition, put a JSON file in this directory with the details of the hit
OUTPUT_JSON = PROJECT_DIR  + "/output/json"
# OUTPUT_CSV (optional, if OUTPUT_JSON specified) - on recnognition, add a line to the CSV file with details of the HIT
OUTPUT_CSV = PROJECT_DIR  + "/output/output.csv"

# DEFAULT_REGION (optional) - The default OpenALPR region (or US state) to try to pattern match license plate strings.
#                             See Open ALPR documentation for more detail
DEFAULT_REGION = "ma"

# MIN_CONF_PATTERNMATCH - Minimum OpenALPR confidence to consider a plate a "hit" when the plate string pattern matches
#                         the pattern for the DEFAULT_REGION
MIN_CONF_PATTERNMATCH = 75.0

# MIN_CONF_PATTERNMATCH - Minimum OpenALPR confidence to consider a plate a "hit" when the plate string pattern does not 
#                         match the pattern for the DEFAULT_REGION
MIN_CONF_NOPATTERNMATCH = 85.0

# RECOGNIZER_THREADS - How many threads to launch to perform recognition. Recommend # of processor cores minus one.
RECOGNIZER_THREADS = 3 # we have four processor cores on the Raspberry Pi 3 Model B

## END DIY-ALPR CONFIG

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
