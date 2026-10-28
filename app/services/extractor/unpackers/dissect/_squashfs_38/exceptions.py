class Error(Exception):
    pass


class NotADirectoryError(Error):
    pass


class NotAFileError(Error):
    pass


class NotASymlinkError(Error):
    pass


class FileNotFoundError(Error):
    pass
