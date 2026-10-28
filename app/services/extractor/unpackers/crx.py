import os
import io
import traceback
import uuid
import struct
from ..interface import *
from ..log import *

class CrxHeader:
    @classmethod
    def parse(cls, stream):
        data = stream.read(8)
        if len(data) != 8:
            return None
        magic, version = struct.unpack('<4sI', data)
        if magic != b'Cr24':
            return None
        
        if version == 2:
            data = stream.read(8)
            if len(data) != 8:
                return None
            public_key_length, signature_length  = struct.unpack('<II', data)
            header = cls()
            header.magic = magic
            header.version = version
            header.public_key_length = public_key_length
            header.signature_length = signature_length
            header.public_key = data[16:16+public_key_length]
            header.signature = data[16+public_key_length:16+public_key_length+signature_length]
            header.size = 16+public_key_length+signature_length
            return header
        elif version == 3:
            """
            chromium/components/crx_file/crx3.proto
            """
            data = stream.read(4)
            if len(data) != 4:
                return None
            file_header_length,  = struct.unpack('<I', data)
            data = stream.read(file_header_length)
            if len(data) != file_header_length:
                return None
            header = cls()
            header.magic = magic
            header.version = version
            header.file_header_length = file_header_length
            header.size = 12+file_header_length
            return header
        return None

class CrxElement(ExtractorElement):
    logger = getLogger('CrxElement')
    def __init__(self, zip_file, zip_info, *, scope, parent_path, max_size_in_mem = -1, temp_dir=None) -> None:
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
        self._stat_mode = (self._zip_info.external_attr >> 16) & 0o777
        
        self._max_size_in_mem = max_size_in_mem
        self._buf = None
        self._temp_path = os.path.join(temp_dir, uuid.uuid4().hex)

        with self._zip_file.open(self._zip_info) as f:
            self._head_bytes = f.read(self.HEADER_BYTES_MAX)

        
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

class CrxUnpacker(Unpacker):
    logger = getLogger('CrxUnpacker')
    @property
    def name(self) -> str:
        return 'CrxUnpacker'
        
    def byte_signatures(self):
        return b'Cr24'

    def is_supported_format(self, context: ExtractorContext, elem: ExtractorElement, head_bytes: bytes) -> bool:
        with elem.open_stream() as stream:
            return CrxHeader.parse(stream) != None

    def extract(self, context: ExtractorContext, elem: ExtractorElement):
        import zipfile

        with ExtractorScope(unpacker=self, context=context, elem=elem) as scope:
            try:
                temp_dir = scope.temp_dir
                with elem.open_stream() as stream:
                    crx_header = CrxHeader.parse(stream)
                    zip_f = zipfile.ZipFile(stream)
                    for info in zip_f.infolist():
                        if scope.should_skip:
                            break
                        if info.is_dir():
                            continue
                        if (info.external_attr >> 16) & 0xA000:  # symbol link
                            continue
                        yield CrxElement(
                            zip_f, info, 
                            max_size_in_mem=1024*1024, temp_dir=temp_dir, 
                            scope=scope, parent_path=elem.qualpath
                        )
            except Exception as exc:
                context.handle_unpacker_exception(exc=exc, elem=elem, logger=self.logger)

