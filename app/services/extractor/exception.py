class ExtractorException(Exception):
    pass

class ExtractorExit(ExtractorException):
    pass

class FormatNotSupported(ExtractorException):
    pass