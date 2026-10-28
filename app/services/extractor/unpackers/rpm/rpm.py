import os

from ...interface import *
from ...log import *


class RpmElement(ExtractorElement):
    def __init__(self, tar_file, tar_member, *, scope, parent_path) -> None:
        super().__init__(scope=scope, parent_path=parent_path)
        self._rpm_file = tar_file
        self._rpm_member = tar_member
        self._name = os.path.split(self._rpm_member.name)[1]
        self._path = self._rpm_member.name
        with self._rpm_file.extractfile(self._rpm_member) as f:
            self._head_bytes = f.read(self.HEADER_BYTES_MAX)
        self._stat_size = self._rpm_member.size
        self._stat_mtime = self._rpm_member.mtime
        self._stat_mode = self._rpm_member.mode

    def open_stream(self):
        return self.StreamWrapper(self, self._rpm_file.extractfile(self._rpm_member))


class RpmUnpacker(Unpacker):
    logger = getLogger('RpmUnpacker')
    @property
    def name(self) -> str:
        return 'RpmUnpacker'
        
    def byte_signatures(self):
        return b'\xed\xab\xee\xdb'

    def is_supported_format(self, context: ExtractorContext, elem: ExtractorElement, head_bytes: bytes) -> bool:
        return head_bytes.startswith(b'\xed\xab\xee\xdb')

    def extract(self, context: ExtractorContext, elem: ExtractorElement):
        from . import rpmfile

        with ExtractorScope(unpacker=self, context=context, elem=elem) as scope:
            try:
                temp_dir = scope.temp_dir
                temp_data_file = os.path.join(temp_dir, 'data')
                with elem.open_stream() as stream:
                    with rpmfile.open(fileobj=stream, temp_data_file=temp_data_file) as rpm_f:
                        for info in rpm_f.getmembers():
                            if scope.should_skip:
                                break
                            if not info.isreg:
                                if info.islink:
                                    context.stats.inc_symlink()
                                continue
                            yield RpmElement(rpm_f, info, scope=scope, parent_path=elem.qualpath)
            except Exception as exc:
                context.handle_unpacker_exception(exc=exc, elem=elem, logger=self.logger)

