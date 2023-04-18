#!/usr/bin/python3

#Libraries
import paho.mqtt.client as mqtt
#import RPi.GPIO as GPIO
import time
from   time import sleep
import datetime
import gc
import json
import os
import sys
#import pigpio
from subprocess import call
from PiicoDev_VL53L1X import PiicoDev_VL53L1X

#GPIO.setwarnings(False)

gc.enable
gc.collect

#set GPIO Pins
GPIO_TRIGGER = 18
GPIO_ECHO = 24

TIME_PAUSE = 25#300

# Referentne vrijednosti u metrima
REF_HEIGHT_VALUE = 2
REF_1 = 0.45425
REF_2 = 0.81457
REF_3 = 1.7552

# Povrsine
P1 = 1.02087
P2 = 1.08823
P3 = 1.13084

GLOBAL_LOG = True

location = os.path.dirname(__file__)+"/" if os.path.dirname(__file__) != "" else ""

with open(location+"settings.json") as json_data:
    data_dict = json.load(json_data)
    
    GPIO_TRIGGER     = data_dict.get("gpio_trigger",0)
    GPIO_ECHO        = data_dict.get("gpio_echo",0)
    TIME_PAUSE       = data_dict.get("time_pause",1)
    REF_HEIGHT_VALUE = data_dict.get("ref_height_value",0)
    REF_1            = data_dict.get("ref1",0)
    REF_2            = data_dict.get("ref2",0)
    REF_3            = data_dict.get("ref3",0)
    P1               = data_dict.get("p1",0)
    P2               = data_dict.get("p2",0)
    P3               = data_dict.get("p3",0)
    GLOBAL_LOG       = data_dict.get("logging",1)
    MQTT_USERNAME    = data_dict.get("mqtt_username","xxx")
    MQTT_PASS        = data_dict.get("mqtt_pass","xxx")

def log_data(p_value):
    if GLOBAL_LOG == 1:
        with open(location+"log.txt","a") as file:
            file.write("{} - {}".format(str(datetime.datetime.now()), p_value)+"\n")

def send_datetime():
    now = datetime.datetime.now()
    sys.stdout.write("Response datetime at - "+ now.strftime("%d.%m.%Y") + " / " + now.strftime("%H:%M:%S") + "\n")
    sys.stdout.write("---------------------------------------------------\n")
    mclient.publish("settings/response", "{} / {}".format(now.strftime("%d.%m.%Y"),now.strftime("%H:%M:%S")), retain=True)

def calculate(dist_m):
    
    input_val = round(REF_HEIGHT_VALUE - dist_m, 2) # trenutna visina goriva u bačvi
    
    sys.stdout.write("trenutna visina goriva " + str(input_val) + " m\n")
    
    out_lit = 0 #yi = REF_HEIGHT_VALUE - input_val
    
    if input_val >= 0 and input_val <= REF_1:
        #sys.stdout.write("calculate h1\n")
        out_lit = ( input_val * P1 ) * 1000 # liters
        
    if input_val >= REF_1 and input_val <= REF_2:
        #sys.stdout.write("calculate h2\n")
        out_lit = ( input_val * P2 ) * 1000 # liters
        
    if input_val >= REF_2 and input_val <= REF_3:
        #sys.stdout.write("calculate h3\n")
        out_lit = ( input_val * P3 ) * 1000 # liters
        
    if input_val >= REF_3 and input_val <= REF_HEIGHT_VALUE:
        #sys.stdout.write("calculate top\n")
        out_lit = REF_HEIGHT_VALUE * 1000 # liters
    
    #sys.stdout.write("\n**************************** \nLitara u tanku " + str(out_lit) + " Lit \n****************************\n\n")    
    
    return round(out_lit, 2)
    
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        sys.stdout.write("Connected successfully!" + "\n")
        log_data("Connected successfully!")
        sleep(1)
        #mclient.publish("tank/read", "xxx", retain=True)
        sys.stdout.write("Publish successfully after connect" + "\n")
        log_data("Publish successfully after connect")
        #mclient.publish("tank/read", "{:.2f}".format(a), retain=True)
        send_datetime()
        sleep(1)
    else:
        sys.stdout.write("Connect returned result code: " + str(rc)+ "\n")
        log_data("Connect returned result code: " + str(rc))


# ############################### MAIN PROGRAM #####################################

if __name__ == '__main__':
    try:
        log_data("App start...")
        sys.stdout.write("App start...\n")
        
        distSensor = PiicoDev_VL53L1X()
        
        # MQTT stuff
        mclient = mqtt.Client(client_id = "Measurement", clean_session = True)
        mclient.username_pw_set(username=MQTT_USERNAME, password=MQTT_PASS)
        mclient.on_connect = on_connect
        mclient.connect("m20.cloudmqtt.com", 11919, keepalive=60)
        mclient.loop_start()
                
        # Measurement stuff
        while True:
            try:
                dist_mm = round(distSensor.read(), 2) # read the distance in millimetres
                #print(str(dist_mm) + " mm")
                dist_cm = dist_mm/10
                dist_m  = dist_cm/100
                
                time.sleep(TIME_PAUSE)
                
                gc.collect
                
                sys.stdout.write ("Measured Distance = " + str(round(dist_cm, 2)) + " cm" + "\n")
                sys.stdout.write ("Measured Distance = " + str(round(dist_m, 2)) + " m" + "\n")
                
                #Calculate to liters -> Volume
                measure_vol = -1
                try:
                    measure_vol = calculate(dist_m)
                    sys.stdout.write("Liters in tank: " + str(measure_vol) + "\n")
                except Exception as e:
                    sys.stdout.write("Error reading measurement: " + str(e) + "\n")
                    log_data("Error reading measurement: " + str(e))
                
                # Send measured value to MQTT
                try:
                    mclient.publish("tank/read", "{:.2f}".format(measure_vol), retain=True)
                    send_datetime()
                    #sys.stdout.write("published successfully"+ "\n")
                except Exception as e:
                    sys.stdout.write("Error sending measurement: " + str(e) + "\n")
                    log_data("Error sending measurement: " + str(e))
                    
            except Exception as e:
                sys.stdout.write("Error in reading distance: " + str(e) + "\n")
                log_data("Error in reading distance: " + str(e))
            
            #sys.stdout.write("--------------------------------------------------------------------\n")
            time.sleep(TIME_PAUSE)

    # Reset by pressing CTRL + C
    except KeyboardInterrupt:
        sys.stdout.write("Measurement stopped by User\n")
        log_data("Measurement stopped by User")
        #GPIO.cleanup()
        mclient.loop_stop()
        mclient.disconnect()
        
    except Exception as e:
        sys.stdout.write("General error " + str(e) + "\n")
        log_data("General error: " + str(e))
        #GPIO.cleanup()
        mclient.loop_stop()
        mclient.disconnect()
        
    mclient.loop_stop()
    mclient.disconnect()
    sys.stdout.write("Closing app...\n")
    log_data("Closing app...")
