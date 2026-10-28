import os
import io

from ...exception import FormatNotSupported
from ...interface import *
from ...log import *
from ...utils import copy_stream_to_file


class CramFSElement(ExtractorElement):
    def __init__(self, fs, path, node, *, scope, parent_path) -> None:
        super().__init__(scope=scope, parent_path=parent_path)
        self._fs = fs
        self._node = node
        self._name = os.path.split(path)[1]
        self._path = path
        self._head_bytes = self._fs.read(self._node)[:self.HEADER_BYTES_MAX]

        self._stat_size = self._node.size
        self._stat_mtime = 0
        self._stat_mode = self._node.mode
        
    def open_stream(self):
        return self.StreamWrapper(
            self, io.BytesIO(self._fs.read(self._node))
        )

class CramFSUnpacker(Unpacker):
    logger = getLogger('CramFSUnpacker')

    def initialize(self, engine: Engine) -> None:
        super().initialize(engine)
        from .cramfs_parser import CramFS

    @property
    def name(self) -> str:
        return 'CramFSUnpacker'

    @property
    def priority(self):
        return -1
        
    def byte_signatures(self):
        return b'\x45\x3d\xcd\x28'

    def is_supported_format(self, context: ExtractorContext, elem: ExtractorElement, head_bytes: bytes) -> bool:
        return head_bytes.startswith(b'\x45\x3d\xcd\x28')

    def extract(self, context: ExtractorContext, elem: ExtractorElement):
        from .cramfs_parser import CramFS
        import stat

        with ExtractorScope(unpacker=self, context=context, elem=elem) as scope:
            try:
                with elem.open_stream() as stream:
                    fs = CramFS(stream)
                    for path, inode in fs.walk():
                        if scope.should_skip:
                            break
                        if not stat.S_ISREG(inode.mode):
                            if stat.S_ISLNK(inode.mode): context.stats.inc_symlink()
                            continue
                        path = path.decode('utf-8')
                        yield CramFSElement(fs, path, inode, scope=scope, parent_path=elem.qualpath)
            except Exception as exc:
                context.handle_unpacker_exception(exc=exc, elem=elem, logger=self.logger)
