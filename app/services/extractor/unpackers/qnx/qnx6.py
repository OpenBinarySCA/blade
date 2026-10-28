import os
import io
import stat

from ...exception import FormatNotSupported
from ...interface import *
from ...log import *
from ...utils import copy_stream_to_file


class QNX6FSElement(ExtractorElement):
    def __init__(self, fs, path, node, *, scope, parent_path) -> None:
        super().__init__(scope=scope, parent_path=parent_path)
        self._fs = fs
        self._node = node
        self._name = os.path.split(path)[1]
        self._path = path
        with node.open() as f:
            self._head_bytes = f.read(self.HEADER_BYTES_MAX)

        self._stat_size = self._node.size
        self._stat_mtime = self._node.mtime
        self._stat_mode = self._node.mode
        self._buf = None
        
    def open_stream(self):
        return self.StreamWrapper(self, self._node.open())

class QNX6FSUnpacker(Unpacker):
    logger = getLogger('QNX6FSUnpacker')

    def initialize(self, engine: Engine) -> None:
        super().initialize(engine)
        from kaitaistruct import KaitaiStream
        from .qnxmount.qnx6.interface import QNX6FS

    @property
    def name(self) -> str:
        return 'QNX6FSUnpacker'

    @property
    def priority(self):
        return -1
        
    def byte_signatures(self):
        return b"\xEB\x10\x90\x00"

    def is_supported_format(self, context: ExtractorContext, elem: ExtractorElement, head_bytes: bytes) -> bool:
        return head_bytes.startswith(self.byte_signatures())

    def extract(self, context: ExtractorContext, elem: ExtractorElement):
        from kaitaistruct import KaitaiStream
        from .qnxmount.qnx6.interface import QNX6FS
        with ExtractorScope(unpacker=self, context=context, elem=elem) as scope:
            try:
                temp_dir = scope.temp_dir
                temp_output_dir = os.path.join(temp_dir, 'output')
                os.mkdir(temp_output_dir)
                if elem.path_in_local_fs:
                    archive_path = elem.path_in_local_fs
                else:
                    archive_path = os.path.join(temp_dir, elem.name)
                    self.logger.debug('<extract> write "%s" to "%s"', elem.qualpath, archive_path)
                    with elem.open_stream() as stream:
                        copy_stream_to_file(stream, archive_path)
                
                with open(archive_path, 'rb') as stream:
                    fs = QNX6FS(KaitaiStream(stream))
                    for node in self._walk(fs):
                        if scope.should_skip:
                            break
                        if not stat.S_ISREG(node.mode):
                            if stat.S_ISLNK(node.mode): context.stats.inc_symlink()
                            continue
                        yield QNX6FSElement(fs, node.path, node, scope=scope, parent_path=elem.qualpath)
            except Exception as exc:
                context.handle_unpacker_exception(exc=exc, elem=elem, logger=self.logger)

    def _walk(self, fs):
        import pathlib
        from .qnxmount.qnx6.interface import QNX6FS
        fs: QNX6FS = fs
        dirstack = []
        dirstack.append((
            '/', fs.get_inode_number_from_path(pathlib.PurePath('/'))
        ))
        while len(dirstack) > 0:
            root_path, root_inode_number = dirstack.pop()
            directory = fs.get_dir(root_inode_number)
            for entry in directory.entries:
                if entry.content.name in ('.', '..'):
                    continue
                inode = fs.get_inode(entry.inode_number)
                #self.logger.debug(f'walk {entry.content.name}')
                if stat.S_ISDIR(inode.mode):
                    dirstack.append((
                        root_path + entry.content.name + '/',
                        entry.inode_number,
                    ))
                    pass
                else:
                    yield FSNode(fs, root_path + entry.content.name, entry.inode_number, inode)
    
import posixpath
class FSNode:
    def __init__(self, fs, path, inode_number, inode) -> None:
        self._fs = fs
        self._path = path
        self._inode_number = inode_number
        self._inode = inode
    @property
    def inode(self):
        return self._inode
    @property
    def size(self):
        return self._inode.size
    @property
    def mtime(self):
        return self._inode.mtime
    @property
    def mode(self):
        return self._inode.mode
    @property
    def path(self):
        return self._path
    @property
    def name(self):
        return posixpath.basename(self._path)

    def open(self):
        if not stat.S_ISREG(self._inode.mode):
            raise Exception('Not a file')
        return FSStream(self)

class FSStream(io.BytesIO):
    def __init__(self, node):
        super().__init__()
        self._fs = node._fs
        self._inode_number = node._inode_number
        self._inode = node._inode
        self._closed = False
        self._pos = 0

    def close(self):
        if self._closed:
            raise Exception('Closed')
    @property
    def closed(self) -> bool:
        return self._closed
    
    def read(self, size=-1) -> bytes:
        if self._pos >= self._inode.size:
            return b''
        if size < 0:
            size = self._inode.size - self._pos
        else:
            size = min(self._inode.size - self._pos, size)
        
        data = self._fs.read_file(self._inode, self._pos, size)
        self._pos += len(data)
        return data
    
    def readable(self) -> bool:
        return True
    
    def seek(self, offset: int, whence: int = io.SEEK_SET) -> int:
        if whence == io.SEEK_SET:
            new_pos = offset
        elif whence == io.SEEK_CUR:
            new_pos = self._pos + offset
        elif whence == io.SEEK_END:
            new_pos = self._inode.size + offset
        else:
            raise ValueError()
        if new_pos >= self._inode.size:
            raise EOFError()
        self._pos = new_pos

    def seekable(self) -> bool:
        return True

    def tell(self) -> int:
        return self._pos
    
    def writable(self) -> bool:
        return False
    

