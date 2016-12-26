import traceback

import time
import math

import gpspoll
import picamera

# set up GPS polling
print "setting up GPS"
try:
	GPS_MAX_AGE = 10
	gpsp = gpspoll.gpspoll()
except:
	print ("Could not start gpspoll")
	traceback.print_exc()
	exit()
	
# initialize the camera
print "setting up camera"
camera = picamera.PiCamera()
camera.exposure_mode = 'auto'
camera.resolution = (1640,1232) #(3280,2464)
CAMERA_USE_VIDEO_PORT = True # Faster, lower-quality capture when using the video port
print "camera set"

# main loop
print "beginning main loop"
try:
	gpsp.start()
	while True:
		data = gpsp.get(GPS_MAX_AGE);
		if (data == None):
			print "no gps fix, skipping photo"
		else:
			#GPSLatitude, GPSLatitudeRef, GPSLongitude, GPSLongitudeRef, and GPSAltitude and GPSAltitudeRef

			print ('- {}: {} {} {}'.format(time.time(), data.longitude, data.latitude, data.altitude))
			camera.exif_tags['GPS.GPSLatitude'] = repr(data.latitude)
			camera.exif_tags['GPS.GPSLatitudeRef'] = "1"
			camera.exif_tags['GPS.GPSLongitude'] = repr(data.longitude)
			camera.exif_tags['GPS.GPSLongitudeRef'] = "1"
			camera.exif_tags['GPS.GPSAltitude'] = repr(data.altitude)
			camera.exif_tags['GPS.GPSAltitudeRef'] = "1"
			camera.exif_tags['GPS.GPS'] = "1"
			gpspoll.deg_to_str(data.longitude)
	
			capture_start = time.time();
			camera.capture('image1.jpg', None, CAMERA_USE_VIDEO_PORT)
			print ("Photo captured in {}s".format(time.time()-capture_start))
		
		time.sleep(3)

except KeyError:
	pass
except (KeyboardInterrupt, SystemExit):
	pass
finally:
	gpsp.stop();
	print "exiting"
