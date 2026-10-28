import os

from ....exception import FormatNotSupported
from ....interface import *
from ....log import *
from ....utils import copy_stream_to_file


class AndroidDynamicPartitionElement(LocalFileSystemElementImpl):
    pass

class AndroidDynamicPartitionUnpacker(Unpacker):
    logger = getLogger('AndroidDynamicPartitionUnpacker')

    def initialize(self, engine: Engine) -> None:
        super().initialize(engine)
        import liblp

    @property
    def name(self) -> str:
        return 'AndroidDynamicPartitionUnpacker'

    @property
    def priority(self):
        return -1
        
    def byte_signatures(self):
        return BYTE_SIGNATURES_FLEXIBLE

    def is_supported_format(self, context: ExtractorContext, elem: ExtractorElement, head_bytes: bytes) -> bool:
        from .lp_format import LP_PARTITION_RESERVED_BYTES, LP_METADATA_GEOMETRY_MAGIC
        import struct
        with elem.open_stream() as stream:
            reserved_bytes = stream.read(LP_PARTITION_RESERVED_BYTES)
            if len(reserved_bytes) != LP_PARTITION_RESERVED_BYTES:
                return False
            magic_bytes = stream.read(4)
            if len(magic_bytes) != 4:
                return False
            if magic_bytes == LP_METADATA_GEOMETRY_MAGIC:
                return True
        return False

    def extract(self, context: ExtractorContext, elem: ExtractorElement):

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
                
                self._extract_to_dir(archive_path, temp_output_dir)
                root_path = os.path.normpath(temp_output_dir)
                for root, dirs, files in os.walk(root_path):
                    for fname in files:
                        fpath = os.path.join(root, fname)
                        relative_path = fpath[len(root_path)+1:]
                        yield AndroidDynamicPartitionElement(relative_path, fpath, scope=scope, parent_path=elem.qualpath)
            except Exception as exc:
                context.handle_unpacker_exception(exc=exc, elem=elem, logger=self.logger)

    def _extract_to_dir(self, input_file_path: str, output_dir: str):
        from liblp.partition_tools.lpunpack import lpunpack
        import pathlib
        lpunpack(
            image = pathlib.Path(input_file_path), 
            output = pathlib.Path(output_dir),
        )