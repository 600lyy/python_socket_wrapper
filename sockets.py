#!/usr/bin/env python3
"""
A client Socket and socket thread that can be used for network communication.
"""
import threading
import socket
import Queue
import errno


class MySocket(object):
    """Standard python socket methods for sending and receiving data.
    """
    def __init__(self, sock=None):
        if sock is None:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        else:
            self.sock = sock
        self.sock.settimeout(0.2)

    def connect(self, host, port):
        self.sock.connect((host, port))

    def close(self):
        self.sock.close()

    def send_data(self, msg):
        totalsent = 0
        while totalsent < len(msg):
            sent = self.sock.send(msg[totalsent:])
            if sent == 0:
                raise RuntimeError("Socket connection broken!")
            totalsent = totalsent + sent

    def receive_data(self, msg_length=4):
        """Receive the given message length from socket.

        Return None if no message can be received. The actual message
        received should never be shorter than the given 'msg_length'.

        :param msg_length: Expected message length as an integer.

        """
        chunks = []
        bytes_recd = 0
        while bytes_recd < msg_length:
            try:
                chunk = self.sock.recv(min(msg_length - bytes_recd, 2048))
            except socket.timeout:      # There is no data to receive.
                return None
            except socket.error as e:
                if e.errno == errno.ECONNRESET:
                    # Connection reset by peer
                    pass
                elif e.errno == errno.EBADF:
                    # Bad file descriptor
                    pass
                else:
                    raise
            else:
                if chunk == '':
                    raise RuntimeError("Socket connection closed by server!")
                chunks.append(chunk)
                bytes_recd = bytes_recd + len(chunk)
        return ''.join(chunks)


class SocketMethods(object):
    """Methods used by the socket thread."""
    def __init__(self, socket):
        self.socket = socket
        self.send_queue = Queue.Queue()
        self.receive_queue = Queue.Queue()

    def get_header(self):
        """Return message header from the socket."""
        return self.socket.receive_data(msg_length=self.header_size)

    def sendfilter(self, msg):
        """Override this method to filter a message placed
        in the send queue before it is sent."""
        return msg

    def receivefilter(self, msg):
        """Override this method to filter a received message
        before it is placed in the receive queue. If this method
        returns ``None``, nothing is placed in the receive queue."""
        return msg

    def get_msg_length(self, header):
        """Override to extract the total message length from a header,
        should return the total message length, including the header as
        an int.

        :param header: The header with length self.header_size

        """
        return self.msg_length

    def handle_socket(self):
        """Handle data on the socket.

        Check the input queue for messages to send and
        also listen for incoming messages to receive.

        If a header size is given, it is returned first and then
        the msg length is extracted with the get_msg_length method.

        """
        try:
            msg = self.send_queue.get_nowait()
            self.socket.send_data(self.sendfilter(msg))
        except Queue.Empty:
            if self.header_size is not None:
                header = self.get_header()
                if header:
                    msg_length = self.get_msg_length(header)
                    msg = header + self.socket.receive_data(msg_length-len(header))
                    if self.receivefilter(msg) is not None:
                        self.receive_queue.put(self.receivefilter(msg))
            elif self.msg_length is not None:
                msg = self.socket.receive_data(self.msg_length)
                if self.receivefilter(msg) is not None:
                    self.receive_queue.put(self.receivefilter(msg))


class SocketThread(threading.Thread, SocketMethods):
    """Continously keep track of messages on a socket.

    When new data have been put in the 'send_queue', the data is fetched from
    the queue and sent via the socket to the server. Likewise, if new data is
    found on the socket, it is fetched and put in the 'receive_queue' where it
    can be accessed from other threads.

    To filter the incoming message, override the ``receivefilter`` method;
    likewise, to filter the outgoing message, override the ``sendfilter`` method.

    If the total size of the message is given in a header, the ``get_msg_length``
    method must also be overridden.

    :param address: A tuple with ip-address (string) and port number (int).
    :param send_queue: An instance of the Queue.Queue class for items to send.
    :param receive_queue: An instance of the Queue.Queue class for items
                          received.
    :param header_size: size of header to fetch.
    :param msg_length: total size of message (used when the message size is fixed)
    :param socket: Socket to use; a new one is created if none is given.

    """
    def __init__(self, *args, **kwargs):
        super(SocketThread, self).__init__()
        self.name = 'SocketThread'
        self.stop_run = False
        self.msg_length = kwargs.pop('msg_length', None)
        self.header_size = kwargs.pop('header_size', None)
        self.send_queue = kwargs.pop('send_queue')
        self.receive_queue = kwargs.pop('receive_queue')
        self.exceptions = kwargs.pop('exceptions', None)
        self.socket = kwargs.pop('socket', None)
        if self.socket is None:
            self.socket = MySocket()
            host, port = kwargs.pop('address')
            self.socket.connect(host, port)
        else:
            self.socket = MySocket(self.socket)

    def stop(self):
        self.socket.close()
        self.stop_run = True

    def run(self):
        while not self.stop_run:
            try:
                self.handle_socket()
            except (TypeError, RuntimeError) as e:
                if self.exceptions is None:
                    raise
                else:
                    self.exceptions.put(e)
                    self.socket.close()
                    self.stop_run = True
