import boto3
import json
import logging
import threading
import select
import socket
import struct
import queue
from socketserver import ThreadingMixIn, TCPServer, StreamRequestHandler

# CONFIG
HOST = '172.29.0.1'
PORT = 9011
region_name='ap-south-1'
tx_url = 'https://sqs.ap-south-1.amazonaws.com/278902205627/Tx-SQS'
rx_url = 'https://sqs.ap-south-1.amazonaws.com/278902205627/Rx-SQS'

# Create SQS client
sqs = boto3.client('sqs', region_name=region_name)

logging.basicConfig(level=logging.INFO)
SOCKS_VERSION = 5
client_closed = False

class ThreadingTCPServer(ThreadingMixIn, TCPServer):
    pass

def sqs_reader(remote_queue):
    while True:
        # wait for remote tunnel to setup connection and reply sqs
        try:
            messages = sqs.receive_message(
                        QueueUrl=rx_url,
                        WaitTimeSeconds=3,
                        MessageAttributeNames=['All'])
            if messages.get('Messages') is None:
                raise Exception("Error connecting to remote")
            for message in messages['Messages']:
                sqs.delete_message(QueueUrl=rx_url, ReceiptHandle=message['ReceiptHandle'])
                if message.get('MessageAttributes') is None:
                    continue
                messageAttributes = message.get('MessageAttributes')
                data = messageAttributes['data']['BinaryValue']
                # print(data.decode('utf-8'))
                remote_queue.put(data)
        except Exception as e:
            if client_closed:
                break

            continue

class SocksProxy(StreamRequestHandler):
    username = 'username'
    password = 'password'

    def handle(self):
        logging.info('Accepting connection from %s:%s' % self.client_address)

        # greeting header
        # read and unpack 2 bytes from a client
        header = self.connection.recv(2)
        version, nmethods = struct.unpack("!BB", header)

        # socks 5
        if version != SOCKS_VERSION or nmethods == 0:
            print("ERR: SOCKS version mismatch")
            exit(1)

        # get available methods
        methods = self.get_available_methods(nmethods)

        # # accept only USERNAME/PASSWORD auth
        # if 2 not in set(methods):
        #     # close connection
        #     self.server.close_request(self.request)
        #     return

        # send welcome message
        self.connection.sendall(struct.pack("!BB", SOCKS_VERSION, 0))

        if 2 in set(methods):
            if not self.verify_credentials():
                print("ERR: failed authentication")
                return

        # request
        version, cmd, _, address_type = struct.unpack("!BBBB", self.connection.recv(4))
        # assert version == SOCKS_VERSION

        if address_type == 1:  # IPv4
            address_string = self.connection.recv(4)
            address = socket.inet_ntoa(address_string)
        elif address_type == 4:  # IPv6
            address_string = self.connection.recv(16)
            address = socket.inet_ntop(socket.AF_INET6, address_string)
        elif address_type == 3:  # Domain name
            #TODO: fixme
            domain_length = self.connection.recv(1)[0]
            address = self.connection.recv(domain_length)
            address = socket.gethostbyname(address)
            address_type = 1 # now its ip
        port = struct.unpack('!H', self.connection.recv(2))[0]

        # reply
        try:
            if cmd == 1:  # CONNECT
                # post connection details to sqs queue
                response = sqs.send_message(
                    QueueUrl=tx_url, MessageBody='hi',
                    MessageAttributes = {
                        'addr_type': {'DataType': 'Number', 'StringValue':str(address_type)},
                        'conn_addr': {'DataType': 'String', 'StringValue':address},
                        'conn_port': {'DataType': 'Number', 'StringValue':str(port)},
                    })

                # wait for remote tunnel to setup connection and reply sqs
                messages = sqs.receive_message(
                            QueueUrl=rx_url,
                            WaitTimeSeconds=20, # FIXME: High TIEMOUT
                            MessageAttributeNames=['All'])
                if messages.get('Messages') is None:
                    raise Exception("Error connecting to remote")
                for message in messages['Messages']:
                    sqs.delete_message(QueueUrl=rx_url, ReceiptHandle=message['ReceiptHandle'])
                    if message.get('MessageAttributes') is None:
                        continue
                    messageAttributes = message.get('MessageAttributes')
                    address_type = messageAttributes.get('addr_type')
                    if address_type is None:
                        raise Exception("Error connecting to remote")
                    address_type = int(messageAttributes.get('addr_type')['StringValue'])
                    reply = messageAttributes.get('conn')['BinaryValue']
            else:
                self.server.close_request(self.request)

        except Exception as err:
            logging.error(err)
            # return connection refused error
            reply = self.generate_failed_reply(address_type, 5)

        self.connection.sendall(reply)

        # establish data exchange
        if reply[1] == 0 and cmd == 1:
            # create local fifo to connect with remote tunnel
            remote_queue = queue.Queue()
            t1 = threading.Thread(target=sqs_reader, args=(remote_queue,))
            t1.start()
            self.exchange_loop(self.connection, remote_queue)

        self.server.close_request(self.request)
    
    def exchange_loop(self, client, remote):
        TIMEOUT = 0.1
        while True:
            # wait until client or remote is available for read
            r, w, e = select.select([client], [], [], TIMEOUT)

            #TODO: receive messages from sqs queue and relay to client
            if client in r:
                data = client.recv(4096)
                if data is None:
                    break
                if len(data) <= 0:
                    logging.info('Client connection closed')
                    #TODO: notify remote that client is closed
                    client_closed = True
                    exit(0)
                    return
                    break
                print("Rx from Sock: ", len(data))
                # post to sqs queue
                response = sqs.send_message(
                    QueueUrl=tx_url, MessageBody='hi',
                    MessageAttributes = {'data': {'DataType': 'Binary', 'BinaryValue':data}})
                print("Tx to SQS: ", len(data))

            try :
                data = remote.get_nowait()
                if data is None:
                    continue
                print("Rx from SQS: ", len(data))
                if client.send(data) <= 0:
                    break
                print("Tx to Sock: ", len(data))
            except Exception as err:
                continue

    def get_available_methods(self, n):
        methods = []
        for i in range(n):
            methods.append(ord(self.connection.recv(1)))
        return methods

    def verify_credentials(self):
        version = ord(self.connection.recv(1))
        # assert version == 1

        username_len = ord(self.connection.recv(1))
        username = self.connection.recv(username_len).decode('utf-8')

        password_len = ord(self.connection.recv(1))
        password = self.connection.recv(password_len).decode('utf-8')

        if username == self.username and password == self.password:
            # success, status = 0
            response = struct.pack("!BB", version, 0)
            self.connection.sendall(response)
            return True

        # failure, status != 0
        response = struct.pack("!BB", version, 0xFF)
        self.connection.sendall(response)
        self.server.close_request(self.request)
        return False

    def generate_failed_reply(self, address_type, error_number):
        return struct.pack("!BBBBIH", SOCKS_VERSION, error_number, 0, address_type, 0, 0)

if __name__ == '__main__':
    try: # clear the tunnel
        messages = sqs.receive_message(
                    QueueUrl=rx_url,
                    WaitTimeSeconds=3, # FIXME: High TIEMOUT
                    MessageAttributeNames=['All'])
        if messages.get('Messages') is None:
            raise Exception("Error connecting to remote")
        for message in messages['Messages']:
            sqs.delete_message(QueueUrl=rx_url, ReceiptHandle=message['ReceiptHandle'])
    except:
        pass

    with ThreadingTCPServer((HOST, PORT), SocksProxy) as server:
        print(f'AWS Proxy running at:  {HOST}:{PORT}')
        server.serve_forever()