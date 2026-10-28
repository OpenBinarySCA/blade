from __future__ import print_function, unicode_literals, absolute_import
from .headers import get_headers
import sys
import io
import gzip
import bz2

try:
    import lzma
except ImportError:
    pass
try:
    import zstandard
except ImportError:
    pass
import struct
from . import cpiofile
from functools import wraps
from .io_extra import _SubFile

pad = lambda fileobj: (4 - (fileobj.tell() % 4)) % 4


class NoLZMAModuleError(NotImplementedError):
    pass


class NoZSTANDARDModuleError(NotImplementedError):
    pass


class NoBytesIOError(NotImplementedError):
    pass


class RPMInfo(object):
    """
    Informational class which holds the details about an
    archive member given by an RPM entry block.
    RPMInfo objects are returned by RPMFile.getmember() and 
    RPMFile.getmembers() and are
    usually created internally.
    """

    _new_coder = struct.Struct(b"8s8s8s8s8s8s8s8s8s8s8s8s8s")

    def __init__(self, name, file_start, file_size, initial_offset, mode, mtime):
        self.name = name
        self.file_start = file_start
        self.size = file_size
        self.initial_offset = initial_offset
        self._mode = mode
        self.mtime = mtime

    @property
    def isdir(self):
        return (self._mode & int("0170000", 8)) == int("0040000", 8)

    @property
    def isreg(self):
        return (self._mode & int("0170000", 8)) == int("0100000", 8)


    @property
    def islink(self):
        return (self._mode & int("0170000", 8)) == int("0120000", 8)
    
    @property
    def mode(self):
        return self._mode & int("0000777", 8)

    def __repr__(self):
        return "<RPMMember %r>" % self.name

    @classmethod
    def _read(cls, magic, fileobj):
        if magic == b"070701":
            return cls._read_new(fileobj, magic=magic)
        else:
            raise Exception("bad magic number %r" % magic)

    @classmethod
    def _read_new(cls, fileobj, magic=None):
        coder = cls._new_coder

        initial_offset = fileobj.tell()
        d = coder.unpack_from(fileobj.read(coder.size))
        
        namesize = int(d[11], 16)
        name = fileobj.read(namesize)[:-1].decode("utf-8")
        fileobj.seek(pad(fileobj), 1)
        file_start = fileobj.tell()
        file_size = int(d[6], 16)
        fileobj.seek(file_size, 1)
        fileobj.seek(pad(fileobj), 1)
        # https://www.mankier.com/5/cpio under Old Binary Format mode bits
        mode = int(d[1], 16)
        mtime = int(d[5], 16)
        # https://manpages.ubuntu.com/manpages/bionic/en/man5/cpio.5.html
        """
            mode    The mode specifies both the regular permissions and the file type.  It consists of
                    several bit fields as follows:
                    0170000  This masks the file type bits.
                    0140000  File type value for sockets.
                    0120000  File type value for symbolic links.  For symbolic links, the link body is
                            stored as file data.
                    0100000  File type value for regular files.
                    0060000  File type value for block special devices.
                    0040000  File type value for directories.
                    0020000  File type value for character special devices.
                    0010000  File type value for named pipes or FIFOs.
                    0004000  SUID bit.
                    0002000  SGID bit.
                    0001000  Sticky bit.  On some systems, this modifies the behavior of executables
                            and/or directories.
                    0000777  The lower 9 bits specify read/write/execute permissions for world, group,
                            and user following standard POSIX conventions.
        """

        return cls(name, file_start, file_size, initial_offset, mode, mtime)


class RPMFile(object):
    """
    Open an RPM archive `name'. `mode' must be 'r' to
    read from an existing archive.
    
    If `fileobj' is given, it is used for reading or writing data. If it
    can be determined, `mode' is overridden by `fileobj's mode.
    `fileobj' is not closed, when TarFile is closed.

    """

    def __init__(self, name=None, mode="rb", fileobj=None, temp_data_file=None):

        if mode != "rb":
            raise NotImplementedError("currently the only supported mode is 'rb'")
        self._fileobj = fileobj or io.open(name, mode)
        self._mode = mode
        self._header_range, self._headers = get_headers(self._fileobj)
        self._ownes_fd = fileobj is None
        self._temp_data_file = temp_data_file

    @property
    def data_offset(self):
        return self._header_range[1]

    @property
    def header_range(self):
        return self._header_range

    @property
    def headers(self):
        "RPM headers"
        return self._headers

    def __enter__(self):
        return self

    def __exit__(self, *excinfo):
        if self._ownes_fd:
            self._fileobj.close()
        if self._temp_data_file:
            if self._data_file:
                self._data_file.close()
                self._data_file = None

    _members = None

    def getmembers(self):
        """
        Return the members of the archive as a list of RPMInfo objects. The
        list has the same order as the members in the archive.
        """
        if self._members is None:
            self._members = _members = []
            g = self.data_file
            magic = g.read(2)
            while magic:
                if magic == b"07":
                    magic += g.read(4)
                    member = RPMInfo._read(magic, g)

                    if member.name == "TRAILER!!!":
                        break

                    if not member.isdir:
                        _members.append(member)

                magic = g.read(2)
            return _members
        return self._members

    def getmember(self, name):
        """
        Return an RPMInfo object for member `name'. If `name' can not be
        found in the archive, KeyError is raised. If a member occurs more
        than once in the archive, its last occurrence is assumed to be the
        most up-to-date version.
        """
        members = self.getmembers()
        for m in members[::-1]:
            if m.name == name:
                return m

        raise KeyError("member %s could not be found" % name)

    def extractfile(self, member):
        """
        Extract a member from the archive as a file object. `member' may be
        a filename or an RPMInfo object.
        The file-like object is read-only and provides the following
        methods: read(), readline(), readlines(), seek() and tell()
        """
        if not isinstance(member, RPMInfo):
            member = self.getmember(member)
        return _SubFile(self.data_file, member.file_start, member.size)

    _data_file = None

    @property
    def data_file(self):
        """Return the uncompressed raw CPIO data of the RPM archive."""

        if self._data_file is None:
            fileobj = _SubFile(self._fileobj, self.data_offset)

            if self.headers["archive_compression"] == b"xz":
                if not getattr(sys.modules[__name__], "lzma", False):
                    raise NoLZMAModuleError("lzma module not present")
                self._data_file = lzma.LZMAFile(fileobj)
            elif self.headers["archive_compression"] == b"zstd":
                if not getattr(sys.modules[__name__], "zstandard", False):
                    raise NoZSTANDARDModuleError("zstandard module not present")
                if not (sys.version_info.major >= 3 and sys.version_info.minor >= 5):
                    raise NoBytesIOError("Need io.BytesIO (Python >= 3.5)")
                with zstandard.ZstdDecompressor().stream_reader(fileobj) as zstd_data:
                    self._data_file = io.BytesIO(zstd_data.read())

            elif self.headers["archive_compression"] == b"bzip2":
                self._data_file = bz2.BZ2File(fileobj)
            else:
                self._data_file = gzip.GzipFile(fileobj=fileobj, mode=self._mode)
            
            if self._temp_data_file:
                from io import open as _io_open
                with _io_open(self._temp_data_file, 'wb+') as f:
                    while True:
                        buf = self._data_file.read(1024*1024)
                        if len(buf) == 0: 
                            break
                        f.write(buf)
                self._data_file.close()
                self._data_file = _io_open(self._temp_data_file, 'rb')

        return self._data_file


def open(name=None, mode="rb", fileobj=None, temp_data_file=None):
    """
    Open an RPM archive for reading. Return
    an appropriate RPMFile class.
    """
    return RPMFile(name, mode, fileobj, temp_data_file)


def main():
    print(sys.argv[1])
    with open(sys.argv[1]) as rpm:
        print(rpm.headers)
        for m in rpm.getmembers():
            print(m)
        print("done")


if __name__ == "__main__":
    main()
