from asyncio import streams
from codecs import ignore_errors
import os
import io


from ...interface import *
from ...log import *


class ArElement(ExtractorElement):
    def __init__(self, ar_f, ar_member, *, scope, parent_path) -> None:
        super().__init__(scope=scope, parent_path=parent_path)
        self._ar_f = ar_f
        self._ar_member = ar_member
        self._name = self._ar_member.name
        self._path = self._name
        with self._ar_f.open(self._ar_member, 'rb') as f:
            self._head_bytes = f.read(self.HEADER_BYTES_MAX)
        self._stat_size = self._ar_member.size
        self._stat_mtime = self._ar_member.timestamp
        self._stat_mode = self._ar_member.mode

    def open_stream(self):
        return self.StreamWrapper(self, self._ar_f.open(self._ar_member, 'rb'))

class ArUnpacker(Unpacker):
    logger = getLogger('ArUnpacker')
    @property
    def name(self) -> str:
        return 'ArUnpacker'
        
    def byte_signatures(self):
        return b"!<arch>\n"

    def is_supported_format(self, context: ExtractorContext, elem: ExtractorElement, head_bytes: bytes) -> bool:
        from .ar import Archive, ArchiveError
        try:
            with elem.open_stream() as f:
                ar_f = Archive(f)
            return True
        except ArchiveError:
            pass
        except:
            pass
        return False

    def extract(self, context: ExtractorContext, elem: ExtractorElement):
        from .ar import Archive, ArchiveError

        with ExtractorScope(unpacker=self, context=context, elem=elem) as scope:
            try:
                with elem.open_stream() as stream:
                    ar_f = Archive(stream)
                    for info in ar_f.entries:
                        if scope.should_skip:
                            break
                        # ar can only contains regular files
                        yield ArElement(ar_f, info, scope=scope, parent_path=elem.qualpath)
            except Exception as exc:
                context.handle_unpacker_exception(exc=exc, elem=elem, logger=self.logger)

