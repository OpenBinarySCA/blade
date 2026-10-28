import os

from ...interface import *
from ...log import *

class FatFSElement(ExtractorElement):
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
        self._stat_mode = 0
        self._buf = None
        
    def open_stream(self):
        return self.StreamWrapper(self, self._node.open())

class FatFSUnpacker(Unpacker):
    logger = getLogger('FatFSUnpacker')
    @property
    def name(self) -> str:
        return 'FatFSUnpacker'
        
    def initialize(self, engine: Engine) -> None:
        super().initialize(engine)
        from dissect.fat import FATFS
        
    def byte_signatures(self):
        return BYTE_SIGNATURES_FLEXIBLE

    def is_supported_format(self, context: ExtractorContext, elem: ExtractorElement, head_bytes: bytes) -> bool:
        from dissect.fat import FATFS
        from dissect.fat.exceptions import Error

        if (elem.stat_size < 1024*1024*1) or (elem.filetype != elem.FILETYPE_UNKNOWN):
            return False
        with elem.open_stream() as stream:
            try:
                fs = FATFS(stream)
            except ValueError as exc:
                return False
            except Error as exc:
                return False
            except NotImplementedError as exc:
                self.logger.info(f'{str(exc)}. {elem.qualpath}')
                return False
            except EOFError:
                return False
        return True

    def extract(self, context: ExtractorContext, elem: ExtractorElement):
        from dissect.fat import FATFS

        with ExtractorScope(unpacker=self, context=context, elem=elem) as scope:
            try:
                with elem.open_stream() as stream:
                    fs = FATFS(stream)
                    for path, node in self._walk_tree(fs.root):
                        if scope.should_skip:
                            break
                        if node.is_directory():
                            continue
                        yield FatFSElement(fs, path, node, scope=scope, parent_path=elem.qualpath)
            except Exception as exc:
                context.handle_unpacker_exception(exc=exc, elem=elem, logger=self.logger)

    def _walk_tree(self, root, parent_path = ''):
        import stat

        for entry in root.iterdir():
            if entry.name == '.': continue
            if entry.name == '..': continue
            yield parent_path + entry.name, entry

            if entry.is_directory():
                yield from self._walk_tree(entry, parent_path = parent_path + entry.name + '/')
            
