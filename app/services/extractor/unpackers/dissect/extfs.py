import os

from ...interface import *
from ...log import *

class ExtFSElement(ExtractorElement):
    def __init__(self, fs, path, node, *, scope, parent_path) -> None:
        super().__init__(scope=scope, parent_path=parent_path)
        self._fs = fs
        self._node = node
        self._name = os.path.split(path)[1]
        self._path = path
        
        with node.open() as f:
            self._head_bytes = f.read(self.HEADER_BYTES_MAX)

        self._stat_size = self._node.size
        self._stat_mtime = int(self._node.mtime.timestamp())
        self._stat_mode = self._node.inode.i_mode
        self._buf = None
        
    def open_stream(self):
        return self.StreamWrapper(self, self._node.open())

class ExtFSUnpacker(Unpacker):
    logger = getLogger('ExtFSUnpacker')
    @property
    def name(self) -> str:
        return 'ExtFSUnpacker'
        
    def initialize(self, engine: Engine) -> None:
        super().initialize(engine)
        from dissect.extfs import ExtFS
        
    def byte_signatures(self):
        return BYTE_SIGNATURES_FLEXIBLE

    def is_supported_format(self, context: ExtractorContext, elem: ExtractorElement, head_bytes: bytes) -> bool:
        from dissect.extfs import ExtFS
        import dissect.extfs.exceptions

        if (elem.stat_size < 1024*1024*1) or (elem.filetype != elem.FILETYPE_UNKNOWN):
            return False
        with elem.open_stream() as stream:
            try:
                fs = ExtFS(stream)
            except dissect.extfs.exceptions.Error as exc:
                return False
            except NotImplementedError as exc:
                self.logger.info(f'{str(exc)}. {elem.qualpath}')
                return False
            except EOFError:
                return False
        return True

    def extract(self, context: ExtractorContext, elem: ExtractorElement):
        from dissect.extfs import ExtFS
        import stat

        with ExtractorScope(unpacker=self, context=context, elem=elem) as scope:
            try:
                with elem.open_stream() as stream:
                    fs = ExtFS(stream)
                    for path, node in self._walk_tree(fs.root):
                        if scope.should_skip:
                            break
                        if not stat.S_ISREG(node.inode.i_mode):
                            if stat.S_ISLNK(node.inode.i_mode): context.stats.inc_symlink()
                            continue
                        yield ExtFSElement(fs, path, node, scope=scope, parent_path=elem.qualpath)
            except Exception as exc:
                context.handle_unpacker_exception(exc=exc, elem=elem, logger=self.logger)

    def _walk_tree(self, root, parent_path = ''):
        import stat
        for name, node in root.listdir().items():
            if node.filename == '.': continue
            if node.filename == '..': continue
            yield parent_path + node.filename, node

            if stat.S_ISDIR(node.inode.i_mode):
                yield from self._walk_tree(node, parent_path + node.filename + '/')
            
