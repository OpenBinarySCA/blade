import os
import io


from ...interface import *
from ...log import *

class CpioElement(ExtractorElement):
    def __init__(self, cpio_file, cpio_member, *, scope, parent_path) -> None:
        super().__init__(scope=scope, parent_path=parent_path)
        self._cpio_file = cpio_file
        self._cpio_member = cpio_member
        self._name = os.path.split(self._cpio_member.name.decode('utf-8'))[1]
        self._path = self._cpio_member.name.decode('utf-8')
        self._head_bytes = self._cpio_member.content[:self.HEADER_BYTES_MAX]
        self._stat_size = self._cpio_member.filesize
        self._stat_mtime = self._cpio_member.mtime
        self._stat_mode = self._cpio_member.mode

    def open_stream(self):
        return self.StreamWrapper(self, io.BytesIO(self._cpio_member.content))


class CpioUnpacker(Unpacker):
    logger = getLogger('CpioUnpacker')
    @property
    def name(self) -> str:
        return 'CpioUnpacker'
        
    def byte_signatures(self):
        from . import cpiofile
        return list(cpiofile._magicmap.keys())

    def is_supported_format(self, context: ExtractorContext, elem: ExtractorElement, head_bytes: bytes) -> bool:
        from . import cpiofile
        try:
            cpiofile.CpioMember.encodedClass(head_bytes)
            return True
        except cpiofile.InvalidFileFormat:
            pass
        return False

    def extract(self, context: ExtractorContext, elem: ExtractorElement):
        from . import cpiofile
        import stat

        with ExtractorScope(unpacker=self, context=context, elem=elem) as scope:
            try:
                with elem.open_stream() as stream:
                    cpio_f = cpiofile.CpioFile()
                    try:
                        cpio_f.open(fileobj=stream)
                    except (cpiofile.InvalidFileFormat, cpiofile.CheckSumError, cpiofile.InvalidFileFormatNull) as exc:
                        self.logger.debug(f'ignore exception: {type(exc).__name__}({str(exc)}), qualpath={elem.qualpath}')
                    for info in cpio_f.members:
                        if scope.should_skip:
                            break
                        if not stat.S_ISREG(info.mode):
                            if stat.S_ISLNK(info.mode): context.stats.inc_symlink()
                            continue
                        yield CpioElement(cpio_f, info, scope=scope, parent_path=elem.qualpath)
            except Exception as exc:
                context.handle_unpacker_exception(exc=exc, elem=elem, logger=self.logger)

