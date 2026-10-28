import abc
import io
import weakref
import traceback
import posixpath

from cffi.cffi_opcode import PRIM_FLOAT

from .filetype import get_file_type_by_bytes
from .log import *

class ExtractorElement(abc.ABC):
    HEADER_BYTES_MAX = 2048
    FILETYPE_UNKNOWN = '???'
    KIND_FILE    = 'file'
    KIND_BLOCK   = 'blk'
    SEEK_CUR = io.SEEK_CUR
    SEEK_SET = io.SEEK_SET
    SEEK_END = io.SEEK_END

    logger = getLogger('ExtractorElement')
    StreamWrapper = None

    def __init__(self, *, scope, parent_path):
        self._opening_streams = set()
        self._scope_ref = weakref.ref(scope)
        self._parent_path = parent_path
        self._kind = self.KIND_FILE
        self._name = None
        self.__path = None
        self._qualpath = None
        self._head_bytes = None
        self._stat_size = None
        self._stat_mtime = None
        self._stat_mode = None
        self._filetype = None
        self._filetype_obj = ''

    @property
    def kind(self) -> str:
        return self._kind

    @property
    def name(self) -> str:
        return self._name

    @property
    def path(self) -> str:
        return self._path

    @property
    def _path(self) -> str:
        return self.__path

    @_path.setter
    def _path(self, string: str) -> str:
        self.__path = posixpath.normpath(string)
        self._qualpath = ElementPath(
            parent = self._parent_path, 
            scope  = self._scope_ref(),
            path   = self.__path,
        )

    @property
    def qualpath(self) -> "ElementPath":
        return self._qualpath

    @property
    def head_bytes(self) -> bytes:
        return self._head_bytes

    @property
    def stat_size(self) -> int:
        return self._stat_size

    @property
    def stat_mtime(self) -> int:
        return self._stat_mtime

    @property
    def stat_mode(self) -> int:
        return self._stat_mode

    @property
    def compressed_size(self) -> int:
        return self.stat_size

    @abc.abstractmethod
    def open_stream(self) -> io.BufferedReader:
        return None

    @property
    def scope(self):
        return self._scope_ref()

    @property
    def path_in_local_fs(self):
        return None

    @property
    def filetype(self):
        ftype = self.filetype_obj
        if ftype:
            return ftype.EXTENSION
        else:
            return self.FILETYPE_UNKNOWN

    @property
    def filetype_attrs(self):
        attrs = get_file_type_by_bytes(self._head_bytes)
        return attrs

    @property
    def filetype_obj(self):
        if self._filetype_obj == '':
            import filetype
            self._filetype_obj = filetype.guess(self.head_bytes)
        return self._filetype_obj

    def destroy(self):
        if len(self._opening_streams):
            self.logger.warn(f'Not all stream closed. count:{len(self._opening_streams)}, qualpath:{self.qualpath}')
            while len(self._opening_streams) > 0:
                stream = self._opening_streams.pop()
                stream.close()
                del stream

    def __del__(self):
        try:
            self.destroy()
        except:
            self.logger.debug(traceback.format_exc())

    def __str__(self):
        return f'<{self.__class__.__name__} {self.qualpath}>'

class _ElementStreamWrapper:
    def __init__(self, elem: ExtractorElement, stream):
        self._elem = elem
        self._stream = stream
        self._elem._opening_streams.add(self)

    def __getattr__(self, name):
        return getattr(self._stream, name)

    def __enter__(self):
        return self

    def __exit__(self, type, value, trace):
        self.close()

    def _untrack(self):
        self._elem._opening_streams.discard(self)

    def close(self): 
        self._stream.close()
        self._untrack()
    
    def __del__(self):
        self.close()

class ElementPath:
    def __init__(self, *, parent: "ElementPath", scope, path: str) -> None:
        self._scope_ref = weakref.ref(scope)
        self._parent = parent
        self._path = path

    def __str__(self) -> str:
        if self._parent != None:
            return str(self._parent) + self._scope_ref().qualsep + self._path
        return self._path


ExtractorElement.StreamWrapper = _ElementStreamWrapper


import os
class LocalFileSystemElementImpl(ExtractorElement):
    def __init__(self, path, local_file, *, scope, parent_path) -> None:
        super().__init__(scope=scope, parent_path=parent_path)
        self._name = os.path.split(path)[1]
        self._path = path
        self._local_file = local_file
        with open(self._local_file, 'rb') as f:
            self._head_bytes = f.read(self.HEADER_BYTES_MAX)
        
        st = os.stat(self._local_file, follow_symlinks=False)
        self._stat_size = st.st_size
        self._stat_mtime = st.st_mtime
        self._stat_mode = st.st_mode

    def open_stream(self):
        return self.StreamWrapper(self, open(self._local_file, 'rb'))

    @property
    def path_in_local_fs(self):
        return self._local_file