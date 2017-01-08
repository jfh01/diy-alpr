import sys
import os
import threading
import re
import time
import csv
import json

import exifread
from openalpr import Alpr

STALE_LOCK_AGE = 120 # ignore/remove locks older than this many seconds

class recognizer (threading.Thread):
    
    min_conf_patternmatch = 75.0
    min_conf_nopatternmatch = 85.0

    lock = None

    def __init__ (self, 
        source_dir, 
        postproc_hit_dir, 
        postproc_nohit_dir, 
        postproc_nohit_lowconf_dir = None, 
        output_json_dir=None, 
        output_csv_file=None, 
        default_region=None,
        lock = None):

        threading.Thread.__init__(self)

        ## save the lock (if specified)
        ## passing in a lock object allows 
        ## multiple recognizer threads to run 
        ## without bumping into each other

        self.lock = lock

        ## check and clean up config
        ## TODO: use os.path to test files and directories, then raise appropriate errors

        self.source_dir = source_dir.rstrip ("/")
        self.postproc_hit_dir = postproc_hit_dir.rstrip ("/")
        self.postproc_nohit_dir = postproc_nohit_dir
        if(self.postproc_nohit_dir):
            self.postproc_nohit_dir = self.postproc_nohit_dir.rstrip ("/")       

        self.postproc_nohit_lowconf_dir = postproc_nohit_lowconf_dir
        if (self.postproc_nohit_lowconf_dir):
            self.postproc_nohit_lowconf_dir = self.postproc_nohit_lowconf_dir.rstrip("/")
        else:
            self.postproc_nohit_lowconf_dir = self.postproc_nohit_dir

        if not(output_json_dir) and not(output_csv_file):
            raise (TypeError('must specify output_csv_file and/or output_json_dir'))
        
        self.output_json_dir = output_json_dir.rstrip ("/")
        self.output_csv_file = output_csv_file

        print "recognizer:init - initializing alpr"
        self.alpr = Alpr("us", "/etc/openalpr/openalpr.conf", "/usr/share/openalpr/runtime_data")
        if not self.alpr.is_loaded():
            print("recognizer:init - error loading OpenALPR")
            sys.exit(1)

        self.alpr.set_top_n(10)

        if (default_region):
            self.alpr.set_default_region(default_region)

        self.running = True
        print "recognizer:init - done initializing alpr"
        
    def __del__ (self):
        print "recognizer:del - unloading alpr"
        self.alpr.unload()
        print "recognizer:del - done"

    def stop(self):
        print "recognizer:stop - waiting for recognizer thread to finish"
        self.running = False
        self.join()
        print "recognizer:stop - recognizer thread finished"

    def run(self):
        tid = self.ident

        while(self.running):
            sys.stdout.flush()
            
            time.sleep(0.05)
            files = sorted(os.listdir(self.source_dir))

#            if (len(files) > 0):
#                print "recognizer:run[{}] - found {} files in {}".format(tid, len(files), self.source_dir)

            for file in files:
                # if we're supposed to be shutting down, then break out of the file processing loop
                if (self.running == False):
                    break

                matches = []
                lowconf_hit = False

                # make sure it looks like one of ours
                if (not(re.match('^\d+(.*)\.jpg$', file))):
                    if file == "README" or file.startswith(".") or re.search('.lock$', file):
                        pass # silently ignore lock files and hidden files
                    else: 
                        print "recognizer:run - ignoring file with bad name {}".format(file)
                else:

                    # to be thread safe, create a lock file while we process
                    img_file = self.source_dir + "/" + file
                    lock_file = img_file + ".lock"

                    # set up file lock while blocking other threads
                    try:
                        if (self.lock):
                            self.lock.acquire()
                        
                        # does the file still exist? if not, skip it silently -- another thread processed already
                        if not(os.path.exists(img_file)):
                            continue

                        # is the file already locked? if so, skip it and say something -- could be another thread working on it or could be a stale lock
                        ## TODO: auto remove old locks
                        try:
                            lock_stat = os.stat(lock_file)
                            if lock_stat: # lock file exists
                                lock_age = time.time() - lock_stat.st_mtime
                                if (lock_age > STALE_LOCK_AGE):
                                    print "recognizer:run - removing stale lock file ({:.0f}s) for {}".format(lock_age, file)
                                    os.unlink(lock_file)
                                else:
                                    continue # file recently locked -- skip it silently
                        except OSError:
                            pass # ignore this error -- indicates lock file doesn't exist

                        # create the lock file
                        with open (lock_file, "w") as f:
                            f.write("{}".format(self.ident))

                    finally:
                        if (self.lock):
                            self.lock.release()


                    # do plate recognition
                    start_time = time.time()
                    results = self.alpr.recognize_file(self.source_dir + "/" + file)
                    recognize_secs = time.time() - start_time
                    print "recognizer:run - recognized {:s} in {:.4f}s found {:2d} possible plates".format(self.source_dir + "/" + file, recognize_secs, len(results['results']))
                    
                    # remove lock file
                    os.remove(lock_file)

                    # review results
                    for plate in results['results']:
                        best_match_plate = None
                        best_match_template = None
                        best_match_confidence = 0.0

                        for candidate in plate['candidates']:
                            if (candidate['matches_template']):
                                if (candidate['confidence'] > self.min_conf_patternmatch and candidate['confidence'] > best_match_confidence):
                                    best_match_plate = candidate['plate']
                                    best_match_confidence = candidate['confidence']
                                    best_match_template = True
                            else:
                                if (candidate['confidence'] > self.min_conf_nopatternmatch and candidate['confidence'] > best_match_confidence):
                                    best_match_plate = candidate['plate']
                                    best_match_confidence = candidate['confidence']
                                    best_match_template = False
                        
                        if (best_match_plate):
                            print "recognizer:run - best match: {} (confidence: {:.3f}, template: {})".format(best_match_plate, best_match_confidence, "yes" if best_match_template else "no")
                            match = {
                                'recognize_time': time.strftime("%Y-%m-%d %H:%M:%S"),
                                'recognize_epoch_time': "{:.0f}".format(start_time),
                                'recognize_secs': "{:0.4f}".format(recognize_secs),
                                'plate': best_match_plate,
                                'confidence': "{:0.2f}".format(best_match_confidence),
                                'matches_template': best_match_template,
                                'file': file
                            }

                            matches.append(match)
                        else:
                            lowconf_hit = True
                            print "recognizer:run - insufficient confidence"

                    # record matches (if any) and move the file away
                    if (len(matches) > 0):

                        # extract GPS and other EXIF data, append to match record, then write output
                        with open(self.source_dir + "/" + file, 'rb') as jpgfile:
                            tags = exifread.process_file(jpgfile, details=False)
                            
                            # extract the image capture date and time
                            if (tags['EXIF DateTimeOriginal']):
                                exif_datetimeoriginal = time.strptime("{}".format(tags['EXIF DateTimeOriginal']), '%Y:%m:%d %H:%M:%S')

                            # extract the GPS coordinates (convert from DMS to DD) and altitude
                            exif_gpslongitude = 0.0
                            exif_gpslatitude = 0.0
                            exif_gpsaltitude = 0
                            tag_lat = tags['GPS GPSLatitude']
                            if (tag_lat and len(tag_lat.values) == 3 and tag_lat.values[0].den > 0):
                                exif_gpslatitude = (float(tag_lat.values[0].num) / float(tag_lat.values[0].den)) + ((float(tag_lat.values[1].num) / float(tag_lat.values[1].den))/60.0) + ((float(tag_lat.values[2].num) / float(tag_lat.values[2].den))/3600.0)
                                exif_gpslatitude *= -1 if (str(tags['GPS GPSLatitudeRef']) == "S") else 1

                            tag_lon = tags['GPS GPSLongitude']
                            if (tag_lon and len(tag_lon.values) == 3 and tag_lon.values[0].den > 0):
                                exif_gpslongitude = (float(tag_lon.values[0].num) / float(tag_lon.values[0].den)) + ((float(tag_lon.values[1].num) / float(tag_lon.values[1].den))/60.0) + ((float(tag_lon.values[2].num) / float(tag_lon.values[2].den))/3600.0)
                                exif_gpslongitude *= -1 if (str(tags['GPS GPSLongitudeRef']) == "W") else 1

                            tag_altitude = tags['GPS GPSAltitude']
                            if (tag_altitude and tag_altitude.values[0].den > 0):
                                exif_gpsaltitude = float(tag_altitude.values[0].num) / float(tag_altitude.values[0].den)

                            # store EXIF data in match records
                            for match in (matches):
                                if(exif_datetimeoriginal):
                                    match['capture_epoch_time'] = '{:.0f}'.format(time.mktime(exif_datetimeoriginal))
                                    match['capture_time'] = time.strftime("%Y-%m-%d %H:%M:%S",exif_datetimeoriginal)
                                else:
                                    match['capture_epoch_time'] = 0
                                    match['capture_time'] = ''
                                
                                match['capture_longitude'] = "{:0.7f}".format(exif_gpslongitude)
                                match['capture_latitude'] = "{:0.7f}".format(exif_gpslatitude)
                                match['capture_altitude_m'] = "{:0.2f}".format(exif_gpsaltitude)

                        # write matches to CSV
                        if (self.output_csv_file):
                            write_header = False if os.access(self.output_csv_file, os.F_OK) else True

                            try:
                                # only one thread can write to the CSV at a time
                                if (self.lock):
                                    self.lock.acquire()

                                with open (self.output_csv_file, "a") as csvfile:
                                    writer = csv.DictWriter(csvfile, ["recognize_time", "recognize_epoch_time", "plate","confidence", "matches_template", "file", "recognize_secs", 'capture_time', 'capture_epoch_time', 'capture_latitude', 'capture_longitude', 'capture_altitude_m'])
                                    if (write_header):
                                        writer.writeheader()

                                    writer.writerow(match)
                            finally:
                                if (self.lock):
                                    self.lock.release()

                        # write JSON (each file is unique, so no thread locking needed)
                        if (self.output_json_dir):
                            json_file = self.output_json_dir + "/" + file[:file.index(".jpg")] + ".json"
                            with open (json_file, "w") as jsonfile:
                                jsonfile.write(json.dumps(matches))            

                        # move the file
                        os.rename (self.source_dir + "/" + file, self.postproc_hit_dir + "/" + file)
                    elif (lowconf_hit): #insufficient confidence
                        if (self.postproc_nohit_lowconf_dir):
                            os.rename (self.source_dir + "/" + file, self.postproc_nohit_lowconf_dir + "/" + file)
                        else:
                            os.unlink(self.source_dir + "/" + file)
                    else: #no hit
                        if (self.postproc_nohit_dir):
                            os.rename (self.source_dir + "/" + file, self.postproc_nohit_dir + "/" + file)
                        else:
                            os.unlink(self.source_dir + "/" + file)

