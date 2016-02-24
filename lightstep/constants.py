"""Constants"""

# Runtime constants
FLUSH_THREAD_NAME = 'Flush Thread'
FLUSH_PERIOD_SECS = 2.5
DEFAULT_MAX_LOG_RECORDS = 1000
DEFAULT_MAX_SPAN_RECORDS = 1000

# Log Keywords
PAYLOAD = 'payload'
SPAN_GUID = 'span_guid'

# Log Levels
INFO_LOG = 'I'
WARN_LOG = 'W'
ERROR_LOG = 'E'
FATAL_LOG = 'F'

# JSON pickle settings
JSON_FAIL = '<Invalid Payload'
JSON_MAX_DEPTH = 32
JSON_UNPICKLABLE = True
JSON_WARNING = True

# utils constants
SECONDS_TO_MICRO = 1000000
