import subprocess
import time
import sys
import meshtastic
import syslog
import meshtastic.serial_interface
from pubsub import pub
from meshtastic.serial_interface import SerialInterface
from meshtastic import portnums_pb2
# SSH Command configuration settings
# The ssh client and server are using public key authentication
USER = 'pi' 
HOST = '192.168.1.60'
CMD = 'boom.sh'
# Response sent back to the node to acknowledge 
send_ack = "Command Ack!"
# List of allowed users
allowed_users = ["mddb", "CWRK"]

serial_port = '/dev/ttyACM0'  # Replace with your Meshtastic device's serial port

def get_node_info(serial_port):
    syslog.syslog("Initializing SerialInterface to get node info...")
    local = SerialInterface(serial_port)
    node_info = local.nodes
    local.close()
    syslog.syslog("Node info retrieved.")
    return node_info

def connect_and_execute():
    subprocess.Popen(f"ssh {USER}@{HOST} {CMD}", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()

def parse_node_info(node_info):
    syslog.syslog("Parsing node info...")
    nodes = []
    for node_id, node in node_info.items():
        nodes.append({
            'num': node_id,
            'user': {
                'shortName': node.get('user', {}).get('shortName', 'Unknown')
            }
        })
    syslog.syslog("Node info parsed.")
    return nodes

def on_receive(packet, interface, node_list):
    try:
        if packet['decoded']['portnum'] == 'TEXT_MESSAGE_APP':
            message = packet['decoded']['payload'].decode('utf-8')
            fromnum = packet['fromId']
            shortname = next((node['user']['shortName'] for node in node_list if node['num'] == fromnum), 'Unknown')
            syslog.syslog(f"{shortname}: {message}")
            if((shortname in allowed_users) and message == 'boom'):
                syslog.syslog(f"Door command came from: {shortname}")
                # Reply back to the sender that the command is acknowledged
                interface.sendText(text=send_ack,destinationId=fromnum,wantAck=True,wantResponse=True)
                # Connect via ssh to the Raspberry Pi and send a command to open the door
                connect_and_execute()
    except KeyError:
        pass  # Ignore KeyError silently
    except UnicodeDecodeError:
        pass  # Ignore UnicodeDecodeError silently

def main():
    syslog.syslog(f"Using serial port: {serial_port}")
    # Retrieve and parse node information
    node_info = get_node_info(serial_port)
    node_list = parse_node_info(node_info)

    # Subscribe the callback function to message reception
    def on_receive_wrapper(packet, interface):
        on_receive(packet, interface, node_list)

    pub.subscribe(on_receive_wrapper, "meshtastic.receive")
    syslog.syslog("Subscribed to meshtastic.receive")

    # Set up the SerialInterface for message listening
    local = SerialInterface(serial_port)
    syslog.syslog("SerialInterface setup for listening.")

    # Keep the script running to listen for messages
    try:
        while True:
            sys.stdout.flush()
            time.sleep(1)  # Sleep to reduce CPU usage
            if(local.stream is None):
                time.sleep(1)
                local.close()
                sys.exit(1)
    except KeyboardInterrupt:
        syslog.syslog("Script terminated by user")
        local.close()

if __name__ == "__main__":
    main()
