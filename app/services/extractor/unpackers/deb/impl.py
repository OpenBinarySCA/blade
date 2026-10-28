import os
import io
import traceback
import uuid
from ...interface import *
from ...log import *


class DebElement(ExtractorElement):
    def __init__(self, prefix, tar_file, tar_member, *, scope, parent_path) -> None:
        super().__init__(scope=scope, parent_path=parent_path)
        self._tar_file = tar_file
        self._tar_member = tar_member
        self._name = os.path.split(self._tar_member.name)[1]
        self._path = prefix + os.path.normpath(self._tar_member.name).replace('\\', '/')
        with self._tar_file.extractfile(self._tar_member) as f:
            self._head_bytes = f.read(self.HEADER_BYTES_MAX)
        self._stat_size = self._tar_member.size
        self._stat_mtime = self._tar_member.mtime
        self._stat_mode = self._tar_member.mode

    def open_stream(self):
        return self.StreamWrapper(self, self._tar_file.extractfile(self._tar_member))

class DebUnpacker(Unpacker):
    logger = getLogger('DebUnpacker')
    @property
    def name(self) -> str:
        return 'DebUnpacker'
        
    def initialize(self, engine: Engine) -> None:
        super().initialize(engine)
        import zstandard
        from ..ar.ar import Archive, ArchiveError
       
    def byte_signatures(self):
        return b'!<arch>\ndebian-'

    def is_supported_format(self, context: ExtractorContext, elem: ExtractorElement, head_bytes: bytes) -> bool:
        return head_bytes.startswith(b'!<arch>\ndebian-binary')

    def extract(self, context: ExtractorContext, elem: ExtractorElement):
        import tarfile
        
        with ExtractorScope(unpacker=self, context=context, elem=elem) as scope:
            try:
                temp_dir = scope.temp_dir
                temp_output_dir = os.path.join(temp_dir, 'output')
                os.mkdir(temp_output_dir)
                self.extract_deb(context=context, elem=elem, output_dir=temp_output_dir)

                with tarfile.TarFile(os.path.join(temp_output_dir, 'control.tar')) as tar_f:
                    for info in tar_f.getmembers():
                        if scope.should_skip:
                            break
                        if info.type != tarfile.REGTYPE:
                            continue
                        yield DebElement('[control]/', tar_f, info, scope=scope, parent_path=elem.qualpath)

                with tarfile.TarFile(os.path.join(temp_output_dir, 'data.tar')) as tar_f:
                    for info in tar_f.getmembers():
                        if scope.should_skip:
                            break
                        if info.type != tarfile.REGTYPE:
                            continue
                        yield DebElement('', tar_f, info, scope=scope, parent_path=elem.qualpath)
            except Exception as exc:
                context.handle_unpacker_exception(exc=exc, elem=elem, logger=self.logger)
                    
    def extract_deb(self, context: ExtractorContext, elem: ExtractorElement, output_dir: str):
        from ..ar.ar import Archive, ArchiveError
        with elem.open_stream() as stream:
            ar_f = Archive(stream)
            if not 'debian-binary' in set(info.name for info in ar_f.entries):
                raise Exception('Not a debian binary file')
            control_member = None
            data_member = None
            for info in ar_f.entries:
                if info.name.startswith('control.tar'):
                    control_member = info
                elif info.name.startswith('data.tar'):
                    data_member = info
            if control_member is None:
                raise Exception('control.tar not found')
            if data_member is None:
                raise Exception('data.tar not found')

            self.extract_member(ar_f, control_member, os.path.join(output_dir, 'control.tar'))
            self.extract_member(ar_f, data_member, os.path.join(output_dir, 'data.tar'))

    def extract_member(self, ar_f, member, output_file):
        from ...utils import copy_stream_to_file
        import gzip
        import bz2
        import lzma
        import zstandard
        if member.name.endswith('.tar'):
            with ar_f.open(member, 'rb') as f:
                copy_stream_to_file(f, output_file)
            return

        with ar_f.open(member, 'rb') as stream:
            if member.name.endswith('.tar.gz'):
                with gzip.GzipFile(fileobj=stream) as decompressed_stream:
                    copy_stream_to_file(decompressed_stream, output_file)
            elif member.name.endswith('.tar.bz2'):
                with bz2.BZ2File(stream) as decompressed_stream:
                    copy_stream_to_file(decompressed_stream, output_file)
            elif member.name.endswith('.tar.xz'):
                with lzma.LZMAFile(stream) as decompressed_stream:
                    copy_stream_to_file(decompressed_stream, output_file)
            elif member.name.endswith('.tar.zst'):
                dctx = zstandard.ZstdDecompressor()
                with open(output_file, 'wb+') as f:
                    dctx.copy_stream(stream, f)
            else:
                raise Exception(f'Unsupported compresss {member.name}')