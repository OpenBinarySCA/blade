import os

from ...interface import *
from ...log import *
from ...utils import copy_stream_to_file
from ..tar import _is_plain_tar_file, TarElement

class CompressedElement(LocalFileSystemElementImpl):
    pass

class CompressedUnpacker(Unpacker):
    logger = getLogger('CompressedUnpacker')
    @property
    def name(self) -> str:
        return 'CompressedUnpacker'

        
    def initialize(self, engine: Engine) -> None:
        super().initialize(engine)

    def byte_signatures(self):
        return (
            b"\x1f\x8b\x08", 
            b"BZh",
            b"\x5d\x00\x00\x80",
            b"\xfd7zXZ",
            b'\x28\xB5\x2F\xFD',
        )

    def is_supported_format(self, context: ExtractorContext, elem: ExtractorElement, head_bytes: bytes) -> bool:
        if head_bytes.startswith(b"\x1f\x8b\x08"):  # gz
            return True
        elif  (head_bytes[0:3] == b"BZh" and head_bytes[4:10] == b"1AY&SY"): #bz2
            return True
        elif head_bytes.startswith((b"\x5d\x00\x00\x80", b"\xfd7zXZ")):  #xz
            return True
        elif head_bytes.startswith(b'\x28\xB5\x2F\xFD'):  #zstd
            return True
        return False

    def extract(self, context: ExtractorContext, elem: ExtractorElement):
        import bz2
        import lzma
        import zstandard
        import tarfile

        with ExtractorScope(unpacker=self, context=context, elem=elem) as scope:    
            try:
                head_bytes = elem.head_bytes
                temp_dir = scope.temp_dir
                # It seems compressed stream can not work properly after seek.
                # Decompress the whole stream to disk
                tmp_file = os.path.join(temp_dir, 'decompressed')
                compressed_size = elem.stat_size if elem.stat_size != -1 else elem.compressed_size
                with elem.open_stream() as stream:
                    if head_bytes.startswith(b"\x1f\x8b\x08"):  # gz
                        format = 'gz'
                        # if mode arg is None, GzipFile will get 'mode' from stream property
                        # some stream object(eg: rpm.extractfile) has a integer property 'mode', 
                        # causing an exception.
                        with GzipFileWithTrailingGarbage(fileobj=stream, mode='rb') as decompressed_stream:
                            copy_stream_to_file(decompressed_stream, tmp_file)
                    elif (head_bytes[0:3] == b"BZh" and head_bytes[4:10] == b"1AY&SY"): #bz2
                        format = 'bz2'
                        with bz2.BZ2File(stream) as decompressed_stream:
                            copy_stream_to_file(decompressed_stream, tmp_file)
                    elif head_bytes.startswith((b"\x5d\x00\x00\x80", b"\xfd7zXZ")):  #xz
                        format = 'xz'
                        with lzma.LZMAFile(stream) as decompressed_stream:
                            copy_stream_to_file(decompressed_stream, tmp_file)
                    elif head_bytes.startswith(b'\x28\xB5\x2F\xFD'):  #zstd
                        format = 'zst'
                        dctx = zstandard.ZstdDecompressor()
                        with open(tmp_file, 'wb+') as f:
                            dctx.copy_stream(stream, f)
                    else:
                        return
                    
                

                with open(tmp_file, 'rb') as f:
                    buf = f.read(ExtractorElement.HEADER_BYTES_MAX)
                
                if _is_plain_tar_file(buf):
                    # Compressed stream can not be random accessed. So every read of tarfile
                    # member will cause a full decompression of input stream (gzip/xz), leading
                    # to a terrible performance problem.
                    # Solution: decompress the tar file first
                    with tarfile.open(tmp_file) as tar_f:
                        for info in tar_f.getmembers():
                            if scope.should_skip:
                                break
                            if info.type != tarfile.REGTYPE:
                                continue
                            yield TarElement(tar_f, info, scope=scope, parent_path=elem.qualpath)
                else:
                    # <name>.<ext>.<format> ->  <name>.<ext>
                    extname = '.' + format
                    if elem.name.endswith(extname):
                        data_name = elem.name[:-len(extname)]
                    else:
                        data_name = format + '-data'
                    yield CompressedElement(data_name, tmp_file, scope=scope, parent_path=elem.qualpath)

            except Exception as exc:
                context.handle_unpacker_exception(exc=exc, elem=elem, logger=self.logger)


"""
gzip命令会忽略结尾的垃圾数据.
例如:
    gzip: ramdisk.gz: decompression OK, trailing garbage ignored

ramdisk结尾带垃圾数据的情况, 可能出现在android bootimg解压后
"""
from .import py38_gzip
class GzipReaderWithTrailingGarbage(py38_gzip._GzipReader):
    def _read_gzip_header(self):
        try:
            return super()._read_gzip_header()
        except py38_gzip.BadGzipFile as exc:
            return None
py38_gzip._GzipReader_old = py38_gzip._GzipReader
py38_gzip._GzipReader = GzipReaderWithTrailingGarbage
GzipFileWithTrailingGarbage = py38_gzip.GzipFile