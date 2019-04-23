""" Connection class establishes HTTP connection with server.
    Utilized to send Proto Report Requests.
"""
import threading
import requests

from lightstep.collector_pb2 import ReportResponse


class _HTTPConnection(object):
    """Instances of _Connection are used to establish a connection to the
    server via HTTP protocol.
    """
    def __init__(self, collector_url, timeout_seconds):
        self._collector_url = collector_url
        self._lock = threading.Lock()
        self.ready = True
        self._timeout_seconds = timeout_seconds

    def open(self):
        """Establish HTTP connection to the server.
        """
        pass

    # May throw an Exception on failure.
    def report(self, *args, **kwargs):
        """Report to the server."""
        auth = args[0]
        report = args[1]
        with self._lock:
            try:
                report.auth.access_token = auth.access_token
                headers = {"Content-Type": "application/octet-stream",
                           "Accept": "application/octet-stream",
                           "Lightstep-Access-Token": auth.access_token}

                r = requests.post(
                    self._collector_url,
                    headers=headers,
                    data=report.SerializeToString(),
                    timeout=self._timeout_seconds)
                resp = ReportResponse()
                resp.ParseFromString(r.content)
                return resp
            except requests.exceptions.RequestException as err:
                raise err

    def close(self):
        """Close HTTP connection to the server."""
        self.ready = False
        pass
