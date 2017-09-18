import os
from cis_interface.drivers.FileDriver import FileDriver


class FileOutputDriver(FileDriver):
    r"""Class to handle output of received messages to a file.

    Args:
        name (str): Name of the output queue to receive messages from.
        args (str): Path to the file that messages should be written to.
        \*\*kwargs: Additional keyword arguments are passed to parent class's
            __init__ method.

    Attributes (in addition to parent class's):
        args (str): Path to the file that messages should be written to.
        fd (file-like): File descriptor for the target file if open.
        lock (:class:`threading.Lock`): Lock to be used when accessing file.

    """
    def __init__(self, name, args, **kwargs):
        super(FileOutputDriver, self).__init__(name, args, suffix="_OUT",
                                               **kwargs)
        self.debug('(%s)', args)

    def run(self):
        r"""Run the driver. The driver will open the file and write receieved
        messages to the file as they are received until the file is closed.
        """
        self.debug(':run in %s', os.getcwd())
        try:
            with self.lock:
                self.fd = open(self.args, 'wb+')
        except:  # pragma: debug
            self.exception('Could not open file.')
            return
        while self.fd is not None:
            data = self.ipc_recv()
            if data is None:  # pragma: debug
                self.debug(':recv: closed')
                break
            self.debug(':recvd %s bytes', len(data))
            if data == self.eof_msg:
                self.debug(':recv: end of file')
                break
            elif len(data) > 0:
                with self.lock:
                    if self.fd is None:
                        break  # pragma: debug
                    else:
                        self.fd.write(data)
            else:
                self.debug(':recv: no data')
                self.sleep()
        self.debug(':run returns')
