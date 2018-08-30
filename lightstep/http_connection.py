""" Connection class establishes HTTP connection with server.
    Utilized to send Proto Report Requests.
"""
import threading
import requests

from lightstep.collector_pb2 import ReportResponse

CONSECUTIVE_ERRORS_BEFORE_RECONNECT = 200


class _HTTPConnection(object):
    """Instances of _Connection are used to establish a connection to the
    server via HTTP protocol.
    """
    def __init__(self, collector_url):
        self._collector_url = collector_url
        self._lock = threading.Lock()
        self.ready = True
        self._report_eof_count = 0
        self._report_consecutive_errors = 0

    def open(self):
        """Establish HTTP connection to the server.
        """
        pass

    # May throw an Exception on failure.
    def report(self, *args, **kwargs):
        """Report to the server."""
        # Notice the annoying case change on the method name. I chose to stay
        # consistent with casing in this class vs staying consistent with the
        # casing of the pass-through method.
        auth = args[0]
        report = args[1]
        with self._lock:
            try:
                report.auth.access_token = auth.access_token
                headers = {"Content-Type": "application/octet-stream",
                           "Accept": "application/octet-stream"}

                r = requests.post(self._collector_url, headers=headers, data=report.SerializeToString())
                resp = ReportResponse()
                resp.ParseFromString(r.content)
                self._report_consecutive_errors = 0
                return resp
            except EOFError:
                self._report_consecutive_errors += 1
                self._report_eof_count += 1
                raise Exception('EOFError')
            finally:
                # In case the client has fallen into an unrecoverable state,
                # recreate the data structure if there are continued report
                # failures
                if self._report_consecutive_errors == CONSECUTIVE_ERRORS_BEFORE_RECONNECT:
                    self._report_consecutive_errors = 0
                    self.ready = False

    def close(self):
        """Close HTTP connection to the server."""
        self.ready = False
        pass
