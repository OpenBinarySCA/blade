import os
import io
import traceback
import uuid
from ...interface import *
from ...log import *


class ZipElement(ExtractorElement):
    logger = getLogger('ZipElement')
    def __init__(self, zip_file, zip_info, *, scope, parent_path, compressed_size, max_size_in_mem = -1, temp_dir=None) -> None:
        super().__init__(scope=scope, parent_path=parent_path)
        self._zip_file = zip_file
        self._zip_info = zip_info
        self._name = os.path.split(self._zip_info.filename)[1]
        self._path = self._zip_info.filename
        
        import datetime
        self._stat_size = self._zip_info.file_size
        try:
            self._stat_mtime = int(datetime.datetime(*self._zip_info.date_time).timestamp())
        except:
            self._stat_mtime = 0
        self._stat_mode = (self._zip_info.external_attr >> 16)
        
        self._max_size_in_mem = max_size_in_mem
        self._buf = None
        self._temp_path = os.path.join(temp_dir, uuid.uuid4().hex)
        self._compressed_size = compressed_size

        with self._zip_file.open(self._zip_info) as f:
            self._head_bytes = f.read(self.HEADER_BYTES_MAX)

        
    @property
    def compressed_size(self) -> int:
        return self._compressed_size

    def open_stream(self):
        if self._stat_size < self._max_size_in_mem:
            if self._buf is None:
                with self._zip_file.open(self._zip_info) as f:
                    self._buf = f.read()
            return self.StreamWrapper(self, io.BytesIO(self._buf))
        else:
            if not os.path.exists(self._temp_path):
                with self._zip_file.open(self._zip_info) as f:
                    with open(self._temp_path, 'wb+') as f_out:
                        while True:
                            buf = f.read(1024*1024)
                            if len(buf) == 0: 
                                break
                            f_out.write(buf)
            return self.StreamWrapper(self, open(self._temp_path, 'rb'))
    
    def destroy(self):
        if self._stat_size < self._max_size_in_mem:
            self._buf = None
        else:
            if os.path.exists(self._temp_path):
                try:
                    os.remove(self._temp_path)
                except OSError as exc:
                    self.logger.warn(f'cleanup tmp file failed.\n\texc: {str(exc)}.\n\tfile:{self._temp_path}')
        super().destroy()

class ZipUnpacker(Unpacker):
    logger = getLogger('ZipUnpacker')
    @property
    def name(self) -> str:
        return 'ZipUnpacker'

    def initialize(self, engine: Engine) -> None:
        try:
            from .zipfile_with_chardet import ZipFile
        except:
            from zipfile import ZipFile
        self._ZipFile = ZipFile

    def byte_signatures(self):
        return b'PK'

    def is_supported_format(self, context: ExtractorContext, elem: ExtractorElement, head_bytes: bytes) -> bool:
        return head_bytes.startswith(b'PK')

    def extract(self, context: ExtractorContext, elem: ExtractorElement):
        import stat

        with ExtractorScope(unpacker=self, context=context, elem=elem) as scope:
            try:
                temp_dir = scope.temp_dir
                with elem.open_stream() as stream:
                    zip_f = self._ZipFile(stream)
                    for info in zip_f.infolist():
                        if scope.should_skip:
                            break
                        if info.is_dir():
                            continue
                        if stat.S_ISLNK(info.external_attr >> 16):  # symbol link
                            context.stats.inc_symlink()
                            continue
                        yield ZipElement(
                            zip_f, info, 
                            compressed_size = info.compress_size,
                            max_size_in_mem=1024*1024, temp_dir=temp_dir, 
                            scope=scope, parent_path=elem.qualpath
                        )
            except Exception as exc:
                context.handle_unpacker_exception(exc=exc, elem=elem, logger=self.logger)
