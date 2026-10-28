import os

from ..interface import *
from ..log import *


class TarElement(ExtractorElement):
    def __init__(self, tar_file, tar_member, *, scope, parent_path) -> None:
        super().__init__(scope=scope, parent_path=parent_path)
        self._tar_file = tar_file
        self._tar_member = tar_member
        self._name = os.path.split(self._tar_member.name)[1]
        self._path = self._tar_member.name
        with self._tar_file.extractfile(self._tar_member) as f:
            self._head_bytes = f.read(self.HEADER_BYTES_MAX)
        self._stat_size = self._tar_member.size
        self._stat_mtime = self._tar_member.mtime
        self._stat_mode = self._tar_member.mode

    def open_stream(self):
        return self.StreamWrapper(self, self._tar_file.extractfile(self._tar_member))


def _is_plain_tar_file(buf):
    import tarfile
    if len(buf) < tarfile.BLOCKSIZE:
        return False
    try:
        tarfile.TarInfo.frombuf(buf[:tarfile.BLOCKSIZE], tarfile.ENCODING, 'surrogateescape')
        return True
    except tarfile.TarError:
        return False

class TarUnpacker(Unpacker):
    logger = getLogger('TarUnpacker')
    @property
    def name(self) -> str:
        return 'TarUnpacker'
        
    def byte_signatures(self):
        return BYTE_SIGNATURES_FLEXIBLE

    def is_supported_format(self, context: ExtractorContext, elem: ExtractorElement, head_bytes: bytes) -> bool:
        return _is_plain_tar_file(head_bytes)

    def extract(self, context: ExtractorContext, elem: ExtractorElement):
        import tarfile
        with ExtractorScope(unpacker=self, context=context, elem=elem) as scope:
            try:
                with elem.open_stream() as stream:
                    tar_f = tarfile.open(fileobj=stream)
                    for info in tar_f.getmembers():
                        if scope.should_skip:
                            break
                        if info.type != tarfile.REGTYPE:
                            continue
                        yield TarElement(tar_f, info, scope=scope, parent_path=elem.qualpath)
            except Exception as exc:
                context.handle_unpacker_exception(exc=exc, elem=elem, logger=self.logger)
