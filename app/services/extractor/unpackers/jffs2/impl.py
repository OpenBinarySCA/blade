import os

from ...interface import *
from ...log import *
from ...utils import copy_stream_to_file


class JFFS2Element(LocalFileSystemElementImpl):
    pass

class JFFS2Unpacker(Unpacker):
    logger = getLogger('JFFS2Unpacker')

    def initialize(self, engine: Engine) -> None:
        super().initialize(engine)
        from ._jefferson_modified import jffs2
        def hacked_print(*args, **kwargs):
            info = ''.join([str(x) for x in args])
            self.logger.debug('<jffs2> ' + info)
        jffs2.print = hacked_print

    @property
    def name(self) -> str:
        return 'JFFS2Unpacker'

    @property
    def priority(self):
        return -1
        
    def byte_signatures(self):
        return [
            b'\x85\x19',
            b'\x84\x19',
            b'\x19\x84',
            b'\x19\x85',
        ]

    def is_supported_format(self, context: ExtractorContext, elem: ExtractorElement, head_bytes: bytes) -> bool:
        return True

    def extract(self, context: ExtractorContext, elem: ExtractorElement):
        import stat

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
                        file_stat = os.stat(fpath, follow_symlinks=False)
                        if not stat.S_ISREG(file_stat.st_mode):
                            if stat.S_ISLNK(file_stat.st_mode):
                                context.stats.inc_symlink()
                            continue
                        yield JFFS2Element(relative_path, fpath, scope=scope, parent_path=elem.qualpath)
            except Exception as exc:
                context.handle_unpacker_exception(exc=exc, elem=elem, logger=self.logger)

    def _extract_to_dir(self, input_file_path: str, output_dir: str):
        from ._jefferson_modified.jffs2 import extract_jffs2
        import pathlib
        extract_jffs2(pathlib.Path(input_file_path), pathlib.Path(output_dir), False)
