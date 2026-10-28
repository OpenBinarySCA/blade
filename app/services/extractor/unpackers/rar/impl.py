import os
import io
from ...interface import *
from ...log import *
from ...utils import copy_stream_to_file


class RarElement(ExtractorElement):
    logger = getLogger('RarElement')
    def __init__(self, rar_file, rar_info, *, scope, parent_path, compressed_size, max_size_in_mem = -1, temp_dir=None) -> None:
        super().__init__(scope=scope, parent_path=parent_path)
        self._rar_file = rar_file
        self._rar_info = rar_info
        self._name = os.path.split(self._rar_info.filename)[1]
        self._path = self._rar_info.filename

        import datetime
        self._stat_size = self._rar_info.file_size
        try:
            self._stat_mtime = int(datetime.datetime(*self._rar_info.date_time).timestamp())
        except:
            self._stat_mtime = 0
        self._stat_mode = 0
        
        self._max_size_in_mem = max_size_in_mem
        self._buf = None
        self._temp_path = None
        self._temp_dir = temp_dir
        self._compressed_size = compressed_size
        
        with self._rar_file.open(self._rar_info) as f:
            self._head_bytes = f.read(self.HEADER_BYTES_MAX)

    @property
    def compressed_size(self) -> int:
        return self._compressed_size

    def open_stream(self):
        if self._stat_size < self._max_size_in_mem:
            if self._buf is None:
                with self._rar_file.open(self._rar_info) as f:
                    self._buf = f.read()
            return self.StreamWrapper(self, io.BytesIO(self._buf))
        else:
            if (not self._temp_path) or (not os.path.exists(self._temp_path)):
                self._temp_path = self._rar_file.extract(self._rar_info, self._temp_dir)
            return self.StreamWrapper(self, open(self._temp_path, 'rb'))
    
    def destroy(self):
        if self._stat_size < self._max_size_in_mem:
            self._buf = None
        else:
            if self._temp_path and os.path.exists(self._temp_path):
                try:
                    os.remove(self._temp_path)
                except OSError as exc:
                    self.logger.warn(f'cleanup tmp file failed.\n\texc: {str(exc)}.\n\tfile:{self._temp_path}')
        super().destroy()

class RarUnpacker(Unpacker):
    logger = getLogger('RarUnpacker')
    @property
    def name(self) -> str:
        return 'RarUnpacker'

    def initialize(self, engine: Engine) -> None:
        return super().initialize(engine)
        
    def byte_signatures(self):
        return b'Rar!'

    def is_supported_format(self, context: ExtractorContext, elem: ExtractorElement, head_bytes: bytes) -> bool:
        if not head_bytes.startswith(b'Rar!'):
            return False
        return True

    def extract(self, context: ExtractorContext, elem: ExtractorElement):
        from ._unrar import rarfile
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
                
                with rarfile.RarFile(archive_path) as rar_f:
                    for info in rar_f.infolist():
                        if scope.should_skip:
                            break
                        if info.is_dir():
                            continue
                        if info.is_lnk():
                            context.stats.inc_symlink()
                            continue
                        yield RarElement(
                            rar_f, info, 
                            compressed_size = info.compress_size,
                            max_size_in_mem=1024*1024, temp_dir=temp_dir, 
                            scope=scope, parent_path=elem.qualpath
                        )
            except Exception as exc:
                context.handle_unpacker_exception(exc=exc, elem=elem, logger=self.logger)
