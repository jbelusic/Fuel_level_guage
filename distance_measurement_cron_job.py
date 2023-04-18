#!/usr/bin/python3

#Libraries
import paho.mqtt.client as mqtt
#import RPi.GPIO as GPIO
import time
from time import sleep
import datetime
import gc
import json
import os
import sys
import smtplib, ssl
import math
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from subprocess import call
from PiicoDev_VL53L1X import PiicoDev_VL53L1X

gc.enable
gc.collect

class Mail:
    ''' Send email class '''
    
    def __init__(self, sender_mail, smtp_server_domain_name, port, password):
        self.sender_mail = sender_mail
        self.smtp_server_domain_name = smtp_server_domain_name
        self.port = port
        self.password = password
        self.val = 0

    def set_val(self, val):
        self.val = val
        
    def send(self, emails):
        ssl_context = ssl.create_default_context()
        service = smtplib.SMTP_SSL(self.smtp_server_domain_name, self.port, context=ssl_context)
        service.login(self.sender_mail, self.password)
        
        for email in emails:
            mail = MIMEMultipart('alternative')
            mail['Subject'] = 'Spremnik goriva'
            mail['From'] = self.sender_mail
            mail['To'] = email

            text_template = """
            ---------------------------------
            Gorivo u tanku je ispod razine od
            {0} litara.
            ---------------------------------
            """
            html_template = """
            ------------------------------------
            <p>Gorivo u tanku je ispod razine od
            </b>
            {0} litara</b>.</p>
            <br\>
            ------------------------------------
            """

            html_content = MIMEText(html_template.format(self.val), 'html')
            text_content = MIMEText(text_template.format(self.val), 'plain')

            mail.attach(text_content)
            mail.attach(html_content)

            service.sendmail(self.sender_mail, email, mail.as_string())

        service.quit()


#GPIO Mode (BOARD / BCM)
#GPIO.setmode(GPIO.BCM)

#set GPIO Pins
GPIO_TRIGGER = 18
GPIO_ECHO = 24

TIME_PAUSE = 1

# Referentne vrijednosti u metrima
REF_HEIGHT_VALUE = 2
REF_1 = 0.45425
REF_2 = 0.81457
REF_3 = 1.7552

# Povrsine
P1 = 1.02087
P2 = 1.08823
P3 = 1.13084

ALERT_FILE = "alert.txt"

# Email config
SEND_EMAIL = 0
SEND_VALUE = 0
EMAIL_FROM = "from_emai@gmail.com"
EMAIL_TO   = "to_email@gmail.com"
EMAIL_PORT = 0
EMAIL_PASS = "xxx"
EMAIL_DOMAIN_NAME = "smtp.gmail.com"

#set GPIO direction (IN / OUT)
#GPIO.setup(GPIO_TRIGGER, GPIO.OUT)
#GPIO.setup(GPIO_ECHO, GPIO.IN)

FILE_LOG   = True
STDOUT_LOG = True

location = os.path.dirname(__file__)+"/" if os.path.dirname(__file__) != "" else ""

with open(location+"settings.json") as json_data:
    data_dict = json.load(json_data)
    
    GPIO_TRIGGER      = data_dict.get("gpio_trigger",0)
    GPIO_ECHO         = data_dict.get("gpio_echo",0)
    TIME_PAUSE        = data_dict.get("time_pause",1)
    REF_HEIGHT_VALUE  = data_dict.get("ref_height_value",0)
    REF_1             = data_dict.get("ref1",0)
    REF_2             = data_dict.get("ref2",0)
    REF_3             = data_dict.get("ref3",0)
    P1                = data_dict.get("p1",0)
    P2                = data_dict.get("p2",0)
    P3                = data_dict.get("p3",0)
    FILE_LOG          = data_dict.get("file_logging",0)
    STDOUT_LOG        = data_dict.get("console_logging",0)
    SEND_EMAIL        = data_dict.get("send_email",0)
    SEND_VALUE        = data_dict.get("send_value",0)
    EMAIL_FROM        = data_dict.get("email_from","xxx@xxx.xx")
    EMAIL_TO          = data_dict.get("email_to","xxx@xxx.xx")
    EMAIL_PORT        = data_dict.get("email_port",0)
    EMAIL_PASS        = data_dict.get("email_pass","xxx")
    EMAIL_DOMAIN_NAME = data_dict.get("email_domain_name","xxx.xxx.xxx")
    MQTT_USERNAME     = data_dict.get("mqtt_username","xxx")
    MQTT_PASS         = data_dict.get("mqtt_pass","xxx")
    
    gc.collect
    
def send_email():
    sys_stdout_write("Preparing email...")
    
    emails = [EMAIL_TO]
    mail = Mail(EMAIL_FROM, EMAIL_DOMAIN_NAME, EMAIL_PORT, EMAIL_PASS)
    mail.set_val(SEND_VALUE)
    mail.send(emails)

    sys_stdout_write("Email sent!\n")

def log_data(p_value):
    if FILE_LOG == 1:
        with open(location+"log.txt","a") as file:
            file.write("{} - {}".format(str(datetime.datetime.now()), p_value)+"\n")
 
def sys_stdout_write(val):
    if STDOUT_LOG:
        sys.stdout.write(val)
            
#--------------------------------------------------------------------------------------------
# Read alert file
#--------------------------------------------------------------------------------------------
def alert_send(measure):
    sys_stdout_write("Ulaz u check alert\n")
    
    val  = 0
    send = False
    
    try:
        with open(location+ALERT_FILE) as file:
            for red in file:
                d = red.split("=")
                
                key = d[0].strip().replace("\r","").replace("\n","").replace("'","") # Prvi podatak (key)
                val = int(d[1].strip().replace("\r","").replace("\n","").replace("'","")) # Drugi podatak (value)
                
                # Ako se tank nadopuni da je preko 500 litara
                if int(measure) > SEND_VALUE and val < SEND_VALUE:
                    val = SEND_VALUE
                
                # Punimo varijable alert podacima
                if key == "ALERT":
                    if int(measure) < val:
                        send = True
        
        sys_stdout_write("Vrijednosti su očitane!\n")
        sys_stdout_write("Stanje u litrama: " + str(val) + "\n")
        
        return send
        
    except Exception as e:
        sys_stdout_write("Error kod alert_send: " + str(e) + "\n")
        log_data("Error kod alert_send: " + str(e)+ "\n") 
        return False
        
#--------------------------------------------------------------------------------------------
# Update alert file
#--------------------------------------------------------------------------------------------
def alert_update(value):
    
    try:                           
        sys_stdout_write("Ulaz u update\n")
        
        x = ""
        l = ""
        new_val = 0
        
        with open(location+ALERT_FILE) as file:
            sys_stdout_write("Otvaram alert file za update\n")
            for line in file:
                l = ""
                x = ""
                l = line.strip()
                
                d = l.split("=")
                try:
                    key = d[0].strip().replace("\r","").replace("\n","").replace("'","") # Prvi podatak (key)
                    val = int(d[1].strip().replace("\r","").replace("\n","").replace("'","")) # Drugi podatak (value)
                    
                    if int(value) > 500:
                        new_val = 500
                    if int(value) < val:
                        new_val = round_down_to_nearest_100(int(value))
                    else:
                        if new_val == 0:
                            new_val = new_val = round_down_to_nearest_100(int(value))
                        else:
                            sys_stdout_write("Nepoznata vrijednost")
                    if int(value) > 0 and key == "ALERT":
                        x = l.replace(l, "ALERT="+str(new_val))
                        with open(location+ALERT_FILE, "w") as file_update:
                            file_update.write(x)
                except Exception as e:
                    sys_stdout_write("Err:" + str(e))
                
        _ = alert_send(value)
        
        sys_stdout_write("Alert je update-an sa " + str(new_val) + "\n")
    except Exception as e:
        sys_stdout_write("Error kod upisa u alert file: " + str(e) + "\n")
        log_data("Error kod upisa u alert file: " + str(e) + "\n") 

def round_down_to_nearest_100(num):
    return math.floor(num / 100) * 100
    
def send_datetime():
    now = datetime.datetime.now()
    sys_stdout_write("Response datetime at - "+ now.strftime("%d.%m.%Y") + " / " + now.strftime("%H:%M:%S") + "\n")
    mclient.publish("settings/response", "{} / {}".format(now.strftime("%d.%m.%Y"),now.strftime("%H:%M:%S")), retain=True)
    

def calculate(dist_m):
    
    sys_stdout_write("REF_HEIGHT_VALUE " + str(REF_HEIGHT_VALUE) + " m\n")
    sys_stdout_write("dist_m " + str(round(dist_m, 2)) + " m\n")
    
    input_val = round(REF_HEIGHT_VALUE - dist_m, 2) # trenutna visina goriva u bačvi
    
    sys_stdout_write("trenutna visina goriva " + str(input_val) + " m\n")
    
    out_lit = 0 #yi = REF_HEIGHT_VALUE - input_val
    
    if input_val >= 0 and input_val <= REF_1:
        sys_stdout_write("calculate h1\n")
        out_lit = ( input_val * P1 ) * 1000 # liters
        
    if input_val >= REF_1 and input_val <= REF_2:
        sys_stdout_write("calculate h2\n")
        out_lit = ( input_val * P2 ) * 1000 # liters
        
    if input_val >= REF_2 and input_val <= REF_3:
        sys_stdout_write("calculate h3\n")
        out_lit = ( input_val * P3 ) * 1000 # liters
        
    if input_val >= REF_3 and input_val <= REF_HEIGHT_VALUE:
        sys_stdout_write("calculate top\n")
        out_lit = REF_HEIGHT_VALUE * 1000 # liters
    
    sys_stdout_write("\n**************************** \nLitara u tanku " + str(out_lit) + " Lit \n****************************\n\n")    
    
    return round(out_lit, 2)
    
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        sys_stdout_write("Connected successfully!" + "\n")
        #log_data("Connected successfully!")
        sleep(1)
        send_datetime()
        sleep(1)
    else:
        sys_stdout_write("Connect returned result code: " + str(rc)+ "\n")
        log_data("Connect returned result code: " + str(rc))
        

# ############################### MAIN PROGRAM #####################################

if __name__ == '__main__':
    try:
        #log_data("App start...")
        sys_stdout_write("App start...\n")
        
        distSensor = PiicoDev_VL53L1X()
        
        # MQTT stuff
        mclient = mqtt.Client(client_id = "Measurement", clean_session = True)
        mclient.username_pw_set(username=MQTT_USERNAME, password=MQTT_PASS)
        mclient.on_connect = on_connect
        mclient.connect("m20.cloudmqtt.com", 11919, keepalive=60)
        mclient.loop_start()
        
        gc.collect
        
        time.sleep(TIME_PAUSE)
        
        # Measurement stuff
        dist_mm = round(distSensor.read(),2) # read the distance in millimetres
        dist_cm = dist_mm/10
        dist_m  = dist_cm/100
        
        sys_stdout_write ("Measured Distance = " + str(round(dist_cm, 2)) + " cm" + "\n")
        sys_stdout_write ("Measured Distance = " + str(round(dist_m, 2)) + " m" + "\n")
        
        time.sleep(TIME_PAUSE)
        
        #Calculate to liters -> Volume
        measure_vol = calculate(round(dist_m,2))

        time.sleep(TIME_PAUSE)
        
        # Send measured value to MQTT
        mclient.publish("tank/read", "{:.2f} Lit / {:.2f} m".format(measure_vol, round(REF_HEIGHT_VALUE - dist_m, 2)), retain=True)
        send_datetime()
        sys_stdout_write("published successfully"+ "\n")
        
        need_to_send = alert_send(measure_vol)
        if need_to_send: #and (measure_vol <= 500 or measure_vol <= 400 or measure_vol <= 300 or measure_vol <= 200 or measure_vol <= 100):
            send_email()
        alert_update(measure_vol)
        
        sys_stdout_write("--------------------------------------------------------------------\n")
        time.sleep(TIME_PAUSE)
        
        mclient.loop_stop()
        mclient.disconnect()

    # Reset by pressing CTRL + C
    except KeyboardInterrupt:
        sys_stdout_write("Measurement stopped by User\n")
        log_data("Measurement stopped by User")
        #GPIO.cleanup()
        mclient.loop_stop()
        mclient.disconnect()
        
    except Exception as e:
        sys_stdout_write("General error " + str(e) + "\n")
        log_data("General error: " + str(e))
        #GPIO.cleanup()
        mclient.loop_stop()
        mclient.disconnect()

#log_data("Closing app...")
sys_stdout_write("Closing app...\n")
gc.collect
