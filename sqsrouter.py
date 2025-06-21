import threading
import boto3
import logging
import json
import select
import socket
import struct
import queue
from time import sleep

# CONFIG
region_name='ap-south-1'
tx_url = 'https://sqs.ap-south-1.amazonaws.com/278902205627/Tx-SQS'
rx_url = 'https://sqs.ap-south-1.amazonaws.com/278902205627/Rx-SQS'

logging.basicConfig(level=logging.INFO)
SOCKS_VERSION = 5

remote_queue = queue.Queue()
# Create SQS client
sqs = boto3.client('sqs', region_name=region_name)

CLOSED = False

def generate_failed_reply(self, address_type, error_number):
    return struct.pack("!BBBBIH", SOCKS_VERSION, error_number, 0, address_type, 0, 0)

def socket_reader(sock, remote_queue):
    TIMEOUT = 0.1
    while not CLOSED:
        # read data from socket and relay the data to the destination
        r, w, e = select.select([sock], [], [], TIMEOUT)
        if sock in r:
            data = sock.recv(4096)
            if len(data) <= 0:
                logging.info('Remote connection closed')
                #TODO: notify remote that client is closed
                exit(1)
                break
            print("Rx from Sock: ", len(data))
            response = sqs.send_message(
                        QueueUrl=rx_url, MessageBody='hi',
                        MessageAttributes = {'data': {'DataType': 'Binary', 'BinaryValue':data}})
            print("Tx to SQS: ", len(data))
        
        # read data from queue and relay the data to the destination
        try:
            data = remote_queue.get_nowait()
            if data is None:
                continue
            print("Tx to Sock: ", len(data))
            if sock.send(data) <=0:
                break
        except Exception as err:
            continue

# if __name__ == '__main__':
while True:
    try:
        messages = sqs.receive_message(
            QueueUrl=tx_url,
            WaitTimeSeconds=5,
            MessageAttributeNames=['All'])
    except Exception as err:
        logging.error(err)
        CLOSED = True
        break

    if messages.get('Messages') is None:
        continue
    for message in messages['Messages']:
        sqs.delete_message(QueueUrl=tx_url, ReceiptHandle=message['ReceiptHandle'])
        if message.get('MessageAttributes') is None:
            continue
        messageAttributes = message.get('MessageAttributes')

        # check headers and create connections
        address_type = messageAttributes.get('addr_type')
        if address_type is not None:
            address_type = int(messageAttributes.get('addr_type')['StringValue'])
            conn_addr = messageAttributes.get('conn_addr')['StringValue']
            conn_port = int(messageAttributes.get('conn_port')['StringValue'])

            try: 
                if address_type == 1:  # IPv4
                    remote = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    # address = socket.inet_ntoa(conn_addr)
                elif address_type == 4:  # IPv6
                    remote = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
                    # address = socket.inet_ntop(socket.AF_INET6, conn_addr)
                remote.connect((conn_addr, conn_port))
                bind_address = remote.getsockname()
                logging.info('Connected to %s %s' % (conn_addr, conn_port))

                # Post to return queue
                if address_type == 1:  # IPv4
                    addr = struct.unpack("!I", socket.inet_aton(bind_address[0]))[0]
                elif address_type == 4:  # IPv6
                    addr = struct.unpack("!8H", socket.inet_pton(socket.AF_INET6, bind_address[0]))[0]
                port = bind_address[1]
                reply = struct.pack("!BBBBIH", SOCKS_VERSION, 0, 0, 1,
                                    addr, port)
                
                # post to return sqs
                response = sqs.send_message(
                    QueueUrl=rx_url, MessageBody='hi',
                    MessageAttributes = {
                        'addr_type': {'DataType': 'Number', 'StringValue':str(address_type)},
                        'conn': {'DataType': 'Binary', 'BinaryValue':reply}
                    })
                
                t1 = threading.Thread(target=socket_reader, args=(remote, remote_queue,))
                t1.start()
            except Exception as err:
                logging.error(err)
                reply = generate_failed_reply(address_type, 5)

            continue

        # relay loop - queue to remote
        data = messageAttributes['data']['BinaryValue']
        # print(data.decode('utf-8'))
        print("Rx from SQS: ", len(data))
        remote_queue.put(data)
        


