# python_socket_wrapper
A generic python socket wrapper using sockect and queue

use like so:

    from python_socket_wapper import SocketThread
    class ClientA(SocketThread):

        def __init__(self):
            self.send_queue = Queue.Queue()
            self.receive_queue = Queue.Queue()
            self.socket_thread = SocketThread(
                                    address=(ip, port),
                                    send_queue=self.send_queue,
                                    receive_queue=self.receive_queue,
                                )
            self.socket_thread.start()
            self.socket_thread.join()

        def send(self, msg):
            self.send_queue.put(msg)

        def receive(self, timeout):
            self.receive_queue.get(timeout=timeout)

        def disconnect(self):
            self.socket_thread.stop()