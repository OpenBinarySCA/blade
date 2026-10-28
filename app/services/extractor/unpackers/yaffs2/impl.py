import os

from ...exception import FormatNotSupported
from ...interface import *
from ...log import *
from ...utils import copy_stream_to_file

class Yaffs2Exception(Exception):
    pass

class Yaffs2Element(LocalFileSystemElementImpl):
    pass

class Yaffs2Unpacker(Unpacker):
    logger = getLogger('Yaffs2Unpacker')

    def initialize(self, engine: Engine) -> None:
        super().initialize(engine)
        import shutil
        self._unyaffs2_path = shutil.which('unyaffs2')
        if not self._unyaffs2_path:
            raise Exception('Can\'t found unyaffs2 command (yaffs2utils)')
        # When processing AndroidAuto.apk(G9), classes.dex will be accepted by yaffs2utils by 
        # accident, and then massive garbage data will be written to disk until the disk is full.
        # This situation indicates that yaffs2utils has some internal logic problems when handling
        # incorrect file format.
        raise Exception('Disabled due to unsolved bug')

    @property
    def name(self) -> str:
        return 'Yaffs2Unpacker'

    @property
    def priority(self):
        return 0
        
    def byte_signatures(self):
        return BYTE_SIGNATURES_WILDCARD

    def is_supported_format(self, context: ExtractorContext, elem: ExtractorElement, head_bytes: bytes) -> bool:
        if elem.filetype_obj:
            return True
        # If decoding is successful, maybe it is a text file
        try:
            text = elem.head_bytes.decode('utf-8')
        except UnicodeDecodeError:
            pass
        else:
            return False

        if elem.stat_size < 1024:
            return False

        return True

    def extract(self, context: ExtractorContext, elem: ExtractorElement):
        import stat

        with ExtractorScope(unpacker=self, context=context, elem=elem) as scope:
            try:
                temp_dir = scope.temp_dir
                temp_stdout_file = os.path.join(temp_dir, 'stdout')
                temp_stderr_file = os.path.join(temp_dir, 'stderr')
                temp_output_dir = os.path.join(temp_dir, 'output')
                os.mkdir(temp_output_dir)
                if elem.path_in_local_fs:
                    archive_path = elem.path_in_local_fs
                else:
                    archive_path = os.path.join(temp_dir, elem.name)
                    self.logger.debug('<extract> write "%s" to "%s"', elem.qualpath, archive_path)
                    with elem.open_stream() as stream:
                        copy_stream_to_file(stream, archive_path)
                
                try:
                    self._extract_to_dir(archive_path, temp_output_dir, temp_stdout_file, temp_stderr_file)
                except Yaffs2Exception:
                    raise FormatNotSupported() from None
                if not os.path.exists(temp_output_dir):
                    raise FormatNotSupported()
                if len(list(os.listdir(temp_output_dir))) == 0:
                    raise FormatNotSupported()
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
                        yield Yaffs2Element(relative_path, fpath, scope=scope, parent_path=elem.qualpath)
            except FormatNotSupported:
                raise
            except Exception as exc:
                context.handle_unpacker_exception(exc=exc, elem=elem, logger=self.logger)

    def _extract_to_dir(self, input_file_path: str, output_dir: str, stdout_file: str, stderr_file: str):
        import subprocess
        import os
        self.logger.debug('<extract_to_dir> extract "%s" to "%s"', input_file_path, output_dir)
        args = [
            self._unyaffs2_path,
            input_file_path,
            output_dir,
        ]
        with open(stdout_file, 'wb+') as stdout_f:
            with open(stderr_file, 'wb+') as stderr_f:
                proc = subprocess.run(
                    args, shell=False, timeout=None, 
                    stdout=stdout_f, stderr=stderr_f,
                )
        
        with open(stderr_file, 'rb') as f:
            stderr = f.read(1024).decode('utf-8', errors='ignore')
        with open(stdout_file, 'rb') as f:
            stdout = f.read(1024).decode('utf-8', errors='ignore')

        if proc.returncode != 0:
            raise Yaffs2Exception(f'unar command failed. returncode: {proc.returncode}\n{stderr}')
                