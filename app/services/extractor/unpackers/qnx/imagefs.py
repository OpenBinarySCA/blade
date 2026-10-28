import os

from ...interface import *
from ...log import *
from ...utils import copy_stream_to_file

class QNXIFSElement(LocalFileSystemElementImpl):
    pass

class QNXIFSUnpacker(Unpacker):
    logger = getLogger('QNXIFSUnpacker')
    @property
    def name(self) -> str:
        return 'QNXIFSUnpacker'
        
    def initialize(self, engine: Engine) -> None:
        super().initialize(engine)
        import shutil
        self._dumpifs_path = shutil.which('dumpifs')
        if not self._dumpifs_path:
            raise Exception('Can\'t found dumpifs command')
       
    def byte_signatures(self):
        return b"imagefs"

    def is_supported_format(self, context: ExtractorContext, elem: ExtractorElement, head_bytes: bytes) -> bool:
        return head_bytes.startswith(b"imagefs")

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
                    self.logger.debug('write "%s" to "%s"', elem.qualpath, archive_path)
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
                        yield QNXIFSElement(relative_path, fpath, scope=scope, parent_path=elem.qualpath)
            except Exception as exc:
                context.handle_unpacker_exception(exc=exc, elem=elem, logger=self.logger)

    def _extract_to_dir(self, input_path, output_dir):
        import subprocess
        self.logger.debug('extract "%s" to "%s"', input_path, output_dir)
        if not os.path.exists(output_dir):
            os.mkdir(output_dir)
        args = [
            self._dumpifs_path,
            input_path,
            '-x'
        ]
        proc = subprocess.run(args, shell=False, cwd=output_dir, capture_output=True)
        stderr = proc.stderr.decode('utf-8') if proc.stderr else ''
        stdout = proc.stdout.decode('utf-8') if proc.stdout else ''
        if stderr:
            self.logger.debug('stderr: %s', stderr)