""" Utility functions
"""
import random
import sys
import time
import math
from . import constants

guid_rng = random.Random()   # Uses urandom seed

def _collector_url_from_hostport(secure, host, port):
    """
    Create an appropriate collector URL given the parameters.

    `secure` should be a bool.
    """
    if secure:
        protocol = 'https://'
    else:
        protocol = 'http://'
    return ''.join([protocol, host, ':', str(port), '/_rpc/v1/reports/binary'])

def _generate_guid():
    """
    Construct a guid - a random 64 bit integer
    """
    return guid_rng.getrandbits(64) - 1

def _id_to_hex(id):
    return '{0:x}'.format(id)

def _now_micros():
    """
    Get the current time in microseconds since the epoch.
    """
    return _time_to_micros(time.time())

def _time_to_micros(t):
    """
    Convert a time.time()-style timestamp to microseconds.
    """
    return math.floor(round(t * constants.SECONDS_TO_MICRO))

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

if sys.version_info[0] == 2:

    # Coerce to ascii (bytes) under Python 2.
    def _coerce_str(val):
        return _coerce_to_bytes(val)
else:

    # Coerce to utf-8 under Python 3.
    def _coerce_str(val):
        return _coerce_to_unicode(val)

def _coerce_to_bytes(val):
    if isinstance(val, bytes):
        return val
    try:
        return val.encode('utf-8', 'replace')
    except Exception:
        try:
            return bytes(val)
        except Exception:
            # Never let these errors bubble up
            return '(encoding error)'

def _coerce_to_unicode(val):
    if isinstance(val, str):
        return val
    try:
        return val.decode('utf-8')
    except Exception:
        try:
            return str(val)
        except Exception:
            # Never let these errors bubble up
            return '(encoding error)'

