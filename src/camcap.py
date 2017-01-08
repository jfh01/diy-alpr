### camcap - captures GPS-tagged photos / videos
import time
import sys
import os
import traceback
import threading

import picamera
import gpspoll

RESOLUTION_LOW = (1640,1232)
RESOLUTION_HIGH = (3280,2464)

PORT_CAMERA = False
PORT_VIDEO = True

MAX_FILES_INITIAL_SLEEP_SECS = .5
MAX_FILES_MAX_SLEEP_SECS = 30.0
MAX_FILES_BACKOFF_FACTOR = 1.25

CTL_FILE_SLEEP_SECS = 3

class camcap (threading.Thread):
    camera_port = PORT_CAMERA
    camera_hflip = False
    camera_vflip = False
    iso = 0
    exposure_mode = 'auto'
    jpg_quality = 85
    resolution = RESOLUTION_HIGH
    gps_max_age = 10
    ctl_file = None

    last_max_files_sleep_secs = None

    def __init__(self):
        threading.Thread.__init__(self)
        
        print "camcap:init - starting"

        # set up GPS polling
        print "camcap:init - setting up GPS"
        try:
            self.gpsp = gpspoll.gpspoll()
        except:
            print ("camcap:init - could not start gpspoll")
            traceback.print_exc()
            exit()
    
    	self.gpsp.start()

        # initialize the camera
        print "camcap:init - setting up camera"
        try:
            self.camera = picamera.PiCamera()
        except:
            print ("camcap:init - could not set up camera")
            traceback.print_exc()
            exit()

        print "camcap:init - done"

    # stop gps thread when camcap object goes away
    def __del__ (self):
        if (self.gpsp):
            print "camcap:del - stopping GPS"
            self.gpsp.stop();
            print "camcap:del - done"
        
    def stop (self):
        print "camcap:stop - waiting for camcap timed capture thread to finish"
        self.running = False
        self.join()
        print "camcap:stop - camcap timed capture thread finished"

        print "camcap:stop - stopping GPS"
        self.gpsp.stop();
        self.gpsp = None
        print "camcap:stop - done"

    def start_auto_capture(self, target_dir, sleep_secs = 1, max_files = None, ctl_file = None):
        self.target_dir = target_dir.rstrip("/")
        ## TODO: check directory and raise error if it's not valid

        self.sleep_secs = sleep_secs
        self.max_files = max_files
        self.ctl_file = ctl_file

        print "camcap:start_auto_capture - launching capture thread"
        self.running = True
        self.start()
        
    def run(self):
        print "camcap:run - auto capture thread running"

        # set camera resolution and orientation
        self.camera.resolution = self.resolution
        self.camera.hflip = self.camera_hflip
        self.camera.vflip = self.camera_vflip
        self.camera.exposure_mode = self.exposure_mode
        self.camera.iso = self.iso

        while(self.running):
            
            # flush stdout (for logging)
            sys.stdout.flush()

            # do our sleep
            time.sleep(self.sleep_secs)
            
            # check if we're at our file limit
            if (self.max_files):
                file_count = len(os.listdir(self.target_dir))

            if (file_count >= self.max_files):
                if self.last_max_files_sleep_secs:
                    sleep_secs = min (MAX_FILES_MAX_SLEEP_SECS, self.last_max_files_sleep_secs * MAX_FILES_BACKOFF_FACTOR)
                else:
                    sleep_secs = MAX_FILES_INITIAL_SLEEP_SECS
                
                print "camcap:run - {} files in target_dir exceeds maximum of {}. sleeping for {:.2f}s.".format(file_count, self.max_files, sleep_secs)

                time.sleep(sleep_secs)

                self.last_max_files_sleep_secs = sleep_secs

                continue # loop until we're below our file limit
            
            # we're not at our file limit
            self.last_max_files_sleep_secs = None
        
            # if a control file is specified, make sure it's present -- otherwise, don't capture
            if self.ctl_file and not(os.path.exists(self.ctl_file)):
                print "camcap:run - control file {} not present, sleeping for {:.2f}s".format(self.ctl_file, CTL_FILE_SLEEP_SECS)
                time.sleep(CTL_FILE_SLEEP_SECS)
                continue # loop until the control file is present

            # capture image into a temp file, then move it to the final file name
            # this keeps the recognizer from trying to parse the file before it's done

            filename = "{:.0f}-{}.jpg".format(time.time() * 1000, os.getpid())
            final_file = self.target_dir + "/" + filename
            capture_file = self.target_dir + "/_tmp." + filename
            if(self.still (capture_file)):
                os.rename (capture_file, final_file)

    # capture a still photo w/ gps -- will exit if no GPS signal is available
    def still (self, file):
            # get GPS data
            data = self.gpsp.get(self.gps_max_age);
            if (data == None):
                print "camcap:still - no gps fix, skipping photo"
                return False

            # set up GPS EXIF tags
            self.camera.exif_tags['GPS.GPSLatitude'] = gpspoll.deg_to_str(data.latitude)
            self.camera.exif_tags['GPS.GPSLatitudeRef'] = 'S' if data.latitude < 0 else 'N'
            self.camera.exif_tags['GPS.GPSLongitude'] = gpspoll.deg_to_str(data.longitude)
            self.camera.exif_tags['GPS.GPSLongitudeRef'] = 'W' if data.longitude < 0 else 'E'
            if (data.altitude):
                self.camera.exif_tags['GPS.GPSAltitude'] = gpspoll.dist_to_str(data.altitude)
                self.camera.exif_tags['GPS.GPSAltitudeRef'] = "0" # assume we're above sea level

            if (data.speed):
                self.camera.exif_tags['GPS.GPSSpeed'] = gpspoll.dist_to_str(data.speed / 1000) # divide to convert mph to kph
                self.camera.exif_tags["GPS.GPSSpeedRef"] = "K"

            #print "camcap:still - EXIF tags: {}".format(self.camera.exif_tags)

            # do capture
            capture_start = time.time();
            self.camera.capture(file, None, self.camera_port, quality=self.jpg_quality)
            print ("camcap:still captured {} in {:.2f}s".format(file, time.time()-capture_start))
            
            return True