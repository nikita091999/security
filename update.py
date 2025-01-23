import subprocess
import time
import json
import paho.mqtt.client as mqtt
import RPi.GPIO as GPIO
import threading
import os
import ssl
import requests
import shutil
import subprocess as sp
import time
import json

BASE_RAW_URL = "https://raw.githubusercontent.com/nikita091999/python_1/main/"
DEPOSIT_DIR = "/home/datamann/deposit"
MAIN_DIR = "/home/datamann/main"
FILES_TO_UPDATE = ["update.py", "config1.json", "version.json"]
VERSION_FILE = os.path.join(MAIN_DIR, "version.json")

BUFFER_FILE = 'buffer_state.json'
arm_state = {"armed": False}  

#+++++++++++++++++++++++GPIO setup++++++++++++++++++++++++++++++++++++++++++++++++
GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)
R1_PIN = 26
R2_PIN = 19
R3_PIN = 13
#R4_PIN = 6

S1_PIN = 20 
S2_PIN = 21  
S3_PIN = 16  
S4_PIN = 12 
D_PIN = 5
HB_PIN = 23
GPIO.setup(D_PIN, GPIO.OUT, initial=GPIO.LOW) 
GPIO.setup(HB_PIN, GPIO.OUT, initial=GPIO.HIGH) 

GPIO.setup(S1_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(S2_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(S3_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(S4_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

GPIO.setup(R1_PIN, GPIO.OUT, initial=GPIO.HIGH)  
GPIO.setup(R2_PIN, GPIO.OUT, initial=GPIO.HIGH)
GPIO.setup(R3_PIN, GPIO.OUT, initial=GPIO.HIGH)  
#GPIO.setup(R4_PIN, GPIO.OUT, initial=GPIO.HIGH)

#+++++++++++++++++++++++++++++++config1 file++++++++++++++++++++++++++++++++++++++++++

try:
    with open('config1.json', 'r') as f:
        config1 = json.load(f)
except FileNotFoundError:
    print('Config1 file not found. Please ensure config1.json is in the current directory.')
    exit()

wifi_config1 = config1.get('wifi', {})
mqtt_config1 = config1.get('mqtt', {})
device_info = config1.get('device_info', {})
sensor_delay = device_info.get('sensor_delay', 2)

topic_hb = f"{device_info['c_code']}/{device_info['a_code']}/{device_info['s_code']}/{device_info['device_id']}/HB"
s_topic = f"{device_info['c_code']}/{device_info['a_code']}/{device_info['s_code']}/{device_info['device_id']}/STJ"
arm_disarm_cc = f"{device_info['c_code']}/{device_info['a_code']}/{device_info['s_code']}/{device_info['device_id']}/CC/D"
reset_topic = f"{device_info['c_code']}/{device_info['a_code']}/{device_info['s_code']}/{device_info['device_id']}/CC/RR"
m_reset_topic = f"{device_info['c_code']}/{device_info['a_code']}/{device_info['s_code']}/{device_info['device_id']}/CC/MR"  
fd_topic = f"{device_info['c_code']}/{device_info['a_code']}/{device_info['s_code']}/{device_info['device_id']}/CC/FD"  
R1_topic = f"{device_info['c_code']}/{device_info['a_code']}/{device_info['s_code']}/{device_info['device_id']}/CC/R1"  
R2_topic = f"{device_info['c_code']}/{device_info['a_code']}/{device_info['s_code']}/{device_info['device_id']}/CC/R2"  
R3_topic = f"{device_info['c_code']}/{device_info['a_code']}/{device_info['s_code']}/{device_info['device_id']}/CC/R3"  
R4_topic = f"{device_info['c_code']}/{device_info['a_code']}/{device_info['s_code']}/{device_info['device_id']}/CC/R4"  

buffer = {
    "ES4007": {"HB":"-1","R1": "0101", "R2": "0102","R3": "0103","R4": "0104","S1": "01","S2": "02","S3": "03","S4": "04","D":"00","RR":"0106","MR":"0107","FD":"0105"}, 
}
#++++++++++++++++++++++ save status ARM and Disram+++++++++++++++++++++++++++++++++++++
def save_buffer_to_file():
    try:
        with open(BUFFER_FILE, 'w') as f:
            json.dump(buffer, f)
        print("Buffer saved successfully:", buffer)
    except Exception as e:
        print("Error saving buffer state:", e)

def load_buffer_from_file():
    global buffer
    try:
        with open(BUFFER_FILE, 'r') as f:
            buffer = json.load(f)
        print("Buffer loaded successfully:", buffer)
    except FileNotFoundError:
        print("Buffer file not found, using default state.")
    except Exception as e:
        print("Error loading buffer state:", e)



#++++++++++++++++++++++++++++++++++ wifi ++++++++++++++++++++++++++++++++++++++++++
def connect_to_wifi(ssid, password, max_attempts=5, retry_delay=10):
    print(f"Connecting to Wi-Fi: {ssid}")
    for attempt in range(max_attempts):
        try:
            subprocess.run(['nmcli', 'dev', 'wifi', 'connect', ssid, 'password', password], check=True)
            print(f"Connected to {ssid}")
            return True
        except subprocess.CalledProcessError:
            print(f"Attempt {attempt + 1}/{max_attempts} failed. Retrying in {retry_delay} seconds...")
            time.sleep(retry_delay)
    print("Failed to connect to Wi-Fi.")
    return False
#++++++++++++++++++++++++++++++++pubslish status+++++++++++++++++++++++++++++++++++++++++++++++++
def publish_status(client):
    try:
        message = json.dumps(buffer)
        client.publish(s_topic, message)
        print(f"Published status: {message} to topic: {s_topic}")
    except Exception as e:
        print(f"Failed to publish status: {e}")
#++++++++++++++++++++++++++++++++++++ HB Topic +++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def publish_heartbeat(client, online=True):
    try:
        GPIO.output(HB_PIN, GPIO.HIGH)  
        heartbeat_status = "1" if online else "-1"
        buffer["ES4007"]["HB"] = heartbeat_status
        #save_buffer_to_file()
        client.publish(topic_hb, heartbeat_status)
        print(f"Published heartbeat status to {topic_hb}: {heartbeat_status}")
    except Exception as e:
        print(f"Failed to publish heartbeat: {e}")
#++++++++++++++++++++++++ machine Reset topic+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def handle_reset(client):
    print("System reset initiated. Rebooting...")
    buffer[device_info['device_id']]["MR"] = "0107" 
    publish_status(client)
    subprocess.run(["sudo", "reboot"])
#++++++++++++++++++++++++++++ FD Topic++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def handle_fd(client, payload):
    if payload == "1105":  
        GPIO.output(R1_PIN, GPIO.HIGH)  
        buffer[device_info['device_id']]["R1"] = "1101"
        buffer[device_info['device_id']]["FD"] = "1105"
        print("FD triggered, turning R1 ON")
    elif payload == "0105":  
        GPIO.output(R1_PIN, GPIO.LOW)  
        buffer[device_info['device_id']]["R1"] = "0101"
        buffer[device_info['device_id']]["FD"] = "0105"
        print("FD default, turning R1 OFF")
    publish_status(client)

#+++++++++++++++++++++++++++++++++++ ARM & Disram++++++++++++++++++++++++++++++++++++++++++++++++++
def handle_arm_disarm(client, payload):
    if payload == "10": 
        arm_state["armed"] = True
        GPIO.output(D_PIN, GPIO.HIGH)
        buffer[device_info['device_id']]["D"] = "10"
        print("System armed. All sensors active.")
    elif payload == "00":  
        arm_state["armed"] = False
        GPIO.output(D_PIN, GPIO.LOW)
        buffer[device_info['device_id']]["D"] = "00"
        print("System disarmed. Sensors inactive. Turning all relays OFF.")
        GPIO.output(R1_PIN, GPIO.HIGH)  
        GPIO.output(R2_PIN, GPIO.HIGH) 
        GPIO.output(R3_PIN, GPIO.HIGH) 
        GPIO.output(R4_PIN, GPIO.HIGH) 
        buffer[device_info['device_id']]["R1"] = "0101"
        buffer[device_info['device_id']]["R2"] = "0102"
        buffer[device_info['device_id']]["R3"] = "0103"
        buffer[device_info['device_id']]["R4"] = "0104"
    save_buffer_to_file() 
    publish_status(client)
#++++++++++++++++++++++++++++++++++++++++ sub topic +++++++++++++++++++++++++++++++++++++++++++++++++++
def on_message(client, userdata, message):
    payload = message.payload.decode('utf-8')
    print(f"Received MQTT message: {payload} on topic: {message.topic}")
               #arm and Disram  
    if message.topic == arm_disarm_cc:
        handle_arm_disarm(client, payload)
        return 
           
    if message.topic == m_reset_topic:  
        handle_reset(client)
        return  
    if message.topic == reset_topic:
        print("Received reset command. Resetting all relays to OFF state.")
        GPIO.output(R1_PIN, GPIO.HIGH)  
        GPIO.output(R2_PIN, GPIO.HIGH) 
        GPIO.output(R3_PIN, GPIO.HIGH)  
        GPIO.output(R4_PIN, GPIO.HIGH) 
        buffer[device_info['device_id']]["R1"] = "0101" 
        buffer[device_info['device_id']]["R2"] = "0102" 
        buffer[device_info['device_id']]["R3"] = "0103"
        buffer[device_info['device_id']]["R4"] = "0104"
        buffer[device_info['device_id']]["FD"] = "0105"
        publish_status(client)  
        return  
    if message.topic == fd_topic:  
        handle_fd(client, payload)
        return  

    if not arm_state["armed"]:
        print("System is disarmed. Ignoring sensor or relay commands.")
        return

    if payload == "1101":
        GPIO.output(R1_PIN, GPIO.LOW)
        buffer[device_info['device_id']]["R1"] = "1101"
        print("R1 ON via MQTT")
    elif payload == "0101":
        GPIO.output(R1_PIN, GPIO.HIGH)
        buffer[device_info['device_id']]["R1"] = "0101"
        print("R1 OFF via MQTT")
    elif payload == "1102":
        GPIO.output(R2_PIN, GPIO.LOW)
        buffer[device_info['device_id']]["R2"] = "1102"
        print("R2 ON via MQTT")
    elif payload == "0102":
        GPIO.output(R2_PIN, GPIO.HIGH)
        buffer[device_info['device_id']]["R2"] = "0102"
        print("R2 OFF via MQTT")

    elif payload == "1103":
        GPIO.output(R3_PIN, GPIO.LOW)
        buffer[device_info['device_id']]["R3"] = "1103"
        print("R3 ON via MQTT")
    elif payload == "0103":
        GPIO.output(R3_PIN, GPIO.HIGH)
        buffer[device_info['device_id']]["R3"] = "0103"
        print("R3 OFF via MQTT")

    elif payload == "1104":
        GPIO.output(R4_PIN, GPIO.LOW)
        buffer[device_info['device_id']]["R4"] = "1104"
        print("R4 ON via MQTT")
    elif payload == "0104":
        GPIO.output(R4_PIN, GPIO.HIGH)
        buffer[device_info['device_id']]["R4"] = "0104"
        print("R4 OFF via MQTT")
    publish_status(client)

def monitor_sensors(client):
    prev_s1 = GPIO.input(S1_PIN)
    prev_s2 = GPIO.input(S2_PIN)
    prev_s3 = GPIO.input(S3_PIN)
    prev_s4 = GPIO.input(S4_PIN)
    while True:
        if not arm_state["armed"]:
            time.sleep(sensor_delay)  
            continue

        current_s1 = GPIO.input(S1_PIN)
        current_s2 = GPIO.input(S2_PIN)
        current_s3 = GPIO.input(S3_PIN)
        current_s4 = GPIO.input(S4_PIN)

        if current_s1 != prev_s1:
            if current_s1 == GPIO.HIGH:
                print("S1 triggered, turning R1 ON")
                GPIO.output(R1_PIN, GPIO.LOW)
                buffer[device_info['device_id']]["R1"] = "1101"
                buffer[device_info['device_id']]["S1"] = "11"

         #   publish_status(client)

        if current_s2 != prev_s2:
            if current_s2 == GPIO.HIGH:
                print("S2 triggered, turning R2 ON")
                GPIO.output(R2_PIN, GPIO.LOW)
                buffer[device_info['device_id']]["R2"] = "1102"
                buffer[device_info['device_id']]["S2"] = "12"

        if current_s3 != prev_s3:
            if current_s3 == GPIO.HIGH:
                print("S3 triggered, turning R3 ON")
                GPIO.output(R3_PIN, GPIO.LOW)
                buffer[device_info['device_id']]["R3"] = "1103"
                buffer[device_info['device_id']]["S3"] = "13"

        if current_s4 != prev_s4:
            if current_s4 == GPIO.HIGH:
                print("S4 triggered, turning R4 ON")
                GPIO.output(R4_PIN, GPIO.LOW)
                buffer[device_info['device_id']]["R4"] = "1104"
                buffer[device_info['device_id']]["S4"] = "14"
            
            publish_status(client)

        prev_s1, prev_s2 = current_s1, current_s2
        
        time.sleep(sensor_delay)
#+++++++++++++++++++++++++++++++ connect mqtt++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++        
def connect_mqtt():
    client = mqtt.Client(protocol=mqtt.MQTTv311)  
    client.tls_set(certfile=None, keyfile=None, cert_reqs=ssl.CERT_NONE, tls_version=ssl.PROTOCOL_TLSv1_2)
    client.username_pw_set(mqtt_config1.get('user'), mqtt_config1.get('password'))
    client.on_message = on_message

    try:
        client.connect(mqtt_config1.get('broker'), mqtt_config1.get('port', 8883))
        print("Connected to MQTT broker")
        client.subscribe([
            (R1_topic, 1),
            (R2_topic, 1),
            (R3_topic, 1),
            (R4_topic, 1),
            (arm_disarm_cc, 1),
            (reset_topic, 1),
            (m_reset_topic, 1),
            (fd_topic, 1)
        ])
        print("Subscribed to MQTT topics")
        client.loop_start()
        threading.Thread(target=monitor_sensors, args=(client,), daemon=True).start()
        
        return client
    except Exception as e:
        print(f"Failed to connect MQTT: {e}")
        exit()

#++++++++++++++++++++++++++++++ ensure_directories in update code +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def ensure_directories():
    for directory in [DEPOSIT_DIR, MAIN_DIR]:
        if not os.path.exists(directory):
            os.makedirs(directory)
            print(f"Created missing directory: {directory}")
#++++++++++++++++++++++++++++++++++++++++++++++download_file++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def download_file(file_name, url, dest_dir):
    try:
        print(f"Downloading {file_name} from {url}...")
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        dest_path = os.path.join(dest_dir, file_name)
        with open(dest_path, "wb") as file:
            file.write(response.content)
        print(f"Updated: {file_name}")
    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error while updating {file_name}: {http_err}")
    except Exception as e:
        print(f"Error updating {file_name}: {e}")
#+++++++++++++++++++++++++++++++++++++++++++++++++++get_current_version++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def get_current_version():
    if os.path.exists(VERSION_FILE):
        with open(VERSION_FILE, "r") as file:
            version_data = json.load(file)
            return version_data.get("version", "")
    return ""
#+++++++++++++++++++++++++++++++++++++++++++++++++++++update_version++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def update_version():
    raw_url = BASE_RAW_URL + "version.json"
    response = requests.get(raw_url, timeout=10)
    if response.status_code == 200:
        latest_version_data = response.json()
        latest_version = latest_version_data.get("version", "")
        current_version = get_current_version()

        if latest_version != current_version:
            print(f"New version found: {latest_version}. Updating files...")
            for file_name in FILES_TO_UPDATE:
                download_file(file_name, BASE_RAW_URL + file_name, MAIN_DIR)
            with open(VERSION_FILE, "w") as file:
                json.dump(latest_version_data, file, indent=4)
            print("Version updated successfully.")
        else:
            print("No new version available. Skipping update.")
    else:
        print(f"Failed to fetch version information from {raw_url}")
#+++++++++++++++++++++++++++++++++++++++++++++++++++++start_updatefile+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

def start_updatefile():
    updatefile_script = "/home/datamann/main/update.py"
    if not os.path.exists(updatefile_script):
        print(f"Warning: {updatefile_script} not found. Skipping update.")
        return None

    return subprocess.Popen(["python3", updatefile_script])
#++++++++++++++++++++++++++++++++++++++++++++++++++monitor_and_update++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

def monitor_and_update(last_version):
    ensure_directories()

    try:
        current_version = update_version()  

        if current_version != last_version:
            print("New version found, updating...")
            update_proc = start_updatefile()

            if update_proc:
                while update_proc.poll() is None:
                    print("Running update.py. Checking for updates in the background...")
                    time.sleep(1)  
                print("update.py process has stopped. Restarting with updated files...")
            else:
                print("Update process not started. Skipping update.")

            return current_version
        else:
            print("No version change detected. Skipping update.")
            return last_version

    except FileNotFoundError as e:
        print(e)
        time.sleep(1) 
        return last_version
    except Exception as e:
        print(f"Error during monitoring: {e}")
        return last_version


def main():
    if connect_to_wifi(wifi_config1.get('ssid'), wifi_config1.get('password')):
        client = connect_mqtt()  
        publish_heartbeat(client, online=True)  
        load_buffer_from_file()

    arm_state_value = buffer.get(device_info['device_id'], {}).get("D", "00")
    print(f"Restored arm state: {arm_state_value}")

    if arm_state_value == "10":
        arm_state["armed"] = True
        GPIO.output(D_PIN, GPIO.HIGH)
        print("System armed on startup.")
    else:
        arm_state["armed"] = False
        GPIO.output(D_PIN, GPIO.LOW)
        print("System disarmed on startup.")

    last_version = None 

    while True:
        last_version = monitor_and_update(last_version)
        message = json.dumps(buffer)
        client.publish(s_topic, message)
        time.sleep(1)  


if __name__ == "__main__":
    main()
