from abc import ABCMeta, abstractmethod


class Converter(object):
    """Converter is a simple abstract interface for converting span data to wire compatible formats for the Satellites.
    """

    __metaclass__ = ABCMeta

    @abstractmethod
    def create_auth(self, access_token):
        pass

    @abstractmethod
    def create_runtime(self, component_name, tags, guid):
        pass

    @abstractmethod
    def create_span_record(self, span, guid):
        pass

    @abstractmethod
    def append_attribute(self, span_record, key, value):
        pass

    @abstractmethod
    def append_join_id(self, span_record, key, value):
        pass

    @abstractmethod
    def append_log(self, span_record, log):
        pass

    @abstractmethod
    def create_report(self, runtime, span_records):
        pass

    @abstractmethod
    def combine_span_records(self, report_request, span_records):
        pass

    @abstractmethod
    def num_span_records(self, report_request):
        pass

    @abstractmethod
    def get_span_records(self, report_request):
        pass

    @abstractmethod
    def get_span_name(self, span_record):
        pass
