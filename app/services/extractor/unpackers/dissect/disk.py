import os

from ...interface import *
from ...log import *
from ...utils import *

class DiskPartitionElement(ExtractorElement):
    def __init__(self, name, partition, *, scope, parent_path) -> None:
        super().__init__(scope=scope, parent_path=parent_path)
        self._kind = self.KIND_BLOCK
        self._partition = partition
        self._name = name
        self._path = name

        with self._partition.open() as f:
            self._head_bytes = f.read(self.HEADER_BYTES_MAX)

        self._stat_size = partition.size
        self._stat_mtime = 0
        self._stat_mode = 0
        
    def open_stream(self):
        return self.StreamWrapper(self, self._partition.open())

class DiskParser(Unpacker):
    logger = getLogger('DiskParser')
    @property
    def name(self) -> str:
        return 'DiskParser'
        
    def initialize(self, engine: Engine) -> None:
        super().initialize(engine)
        from dissect.volume.disk import Disk
        
    @property
    def priority(self):
        return -1

    def byte_signatures(self):
        return BYTE_SIGNATURES_FLEXIBLE

    def is_supported_format(self, context: ExtractorContext, elem: ExtractorElement, head_bytes: bytes) -> bool:
        from dissect.volume.disk import Disk
        from dissect.volume.exceptions import DiskError

        if context.current_unpacker() == self.name:
            return False

        if (elem.stat_size < 1024*1024*1) or (elem.filetype != elem.FILETYPE_UNKNOWN):
            return False
        with elem.open_stream() as stream:
            try:
                disk = Disk(stream)
                # maybe it's a volume with VBR, there is no way to be sure.
                if len(disk.partitions) == 0:
                    return False
            except DiskError as exc:
                return False
            except NotImplementedError as exc:
                self.logger.warning(f'{str(exc)}. {elem.qualpath}')
                return False
            except EOFError:
                return False
        return True

    def extract(self, context: ExtractorContext, elem: ExtractorElement):
        from dissect.volume.disk import Disk

        with ExtractorScope(unpacker=self, context=context, elem=elem) as scope:
            try:
                temp_dir = scope.temp_dir
                if elem.path_in_local_fs:
                    temp_disk_path = elem.path_in_local_fs
                else:
                    temp_disk_path = os.path.join(temp_dir, elem.name)
                    self.logger.debug('<extract> write "%s" to "%s"', elem.qualpath, temp_disk_path)
                    with elem.open_stream() as stream:
                        copy_stream_to_file(stream, temp_disk_path)
                
                with open(temp_disk_path, 'rb') as stream:
                    disk = Disk(stream)
                    for partition in disk.partitions:
                        if scope.should_skip:
                            break
                        yield DiskPartitionElement(f'partition-{partition.offset:0x}', partition, scope=scope, parent_path=elem.qualpath)
                 
            except Exception as exc:
                context.handle_unpacker_exception(exc=exc, elem=elem, logger=self.logger)

