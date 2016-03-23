""" Utility functions
"""
import uuid
import time
from . import constants

def _service_url_from_hostport(secure, host, port):
    """
    Create an appropriate service URL given the parameters.

    `secure` should be a bool.
    """
    if secure:
        protocol = 'https://'
    else:
        protocol = 'http://'
    return ''.join([protocol, host, ':', str(port), '/_rpc/v1/reports/binary'])

def _generate_guid():
    """
    Construct a guid - random 64 bit integer converted to a string.
    """
    # Note: uuid.uuid4() returns 128 bit int. To get 64 bit int, apply the mask.
    guid = uuid.uuid4().int & (1<<64)-1
    return str(guid)

def _now_micros():
    """
    Get the current time in microseconds since the epoch.
    """
    return _time_to_micros(time.time())

def _time_to_micros(t):
    """
    Convert a time.time()-style timestamp to microseconds.
    """
    return long(round(time.time() * constants.SECONDS_TO_MICRO))

def _merge_dicts(*dict_args):
    """Destructively merges dictionaries, returns None instead of an empty dictionary.

    Elements of dict_args can be None.
    Keys in latter dicts override those in earlier ones.
    """
    result = {}
    for dictionary in dict_args:
        if dictionary:
            result.update(dictionary)
    return result if result else None
