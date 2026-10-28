import os

from ..exception import FormatNotSupported
from ..interface import *
from ..log import *
from ..utils import copy_stream_to_file

class UnarException(Exception):
    pass

class UnarElement(LocalFileSystemElementImpl):
    pass

class UnarWrapper(Unpacker):
    logger = getLogger('UnarWrapper')

    def initialize(self, engine: Engine) -> None:
        super().initialize(engine)
        import shutil
        self._unar_path = shutil.which('unar')
        if not self._unar_path:
            raise Exception('Can\'t found unar command')

    @staticmethod
    def _win_search_file_in_path(name):
        import os
        for dir in os.getenv('PATH').split(';'):
            dir = dir.strip()
            if len(dir) == 0: continue
            p = os.path.join(dir, name)
            if os.path.exists(p):
                return p
        return None

    @property
    def name(self) -> str:
        return 'UnarWrapper'

    @property
    def priority(self):
        return -1
        
    def byte_signatures(self):
        return BYTE_SIGNATURES_WILDCARD

    def is_supported_format(self, context: ExtractorContext, elem: ExtractorElement, head_bytes: bytes) -> bool:
        if elem.filetype_obj:
            mime = elem.filetype_obj.mime
            if mime.startswith('audio') or mime.startswith('video') or mime.startswith('image'):
                return False
            if elem.filetype_obj.extension.lower() in ('elf', ):
                return False
            if elem.filetype_obj.extension in (
                             'rar', '7z', 'crx', 'cab', 
                             'ar', 'z', 'lzo', 'lz', 'lz4', 'zst'
                             ):
                return True
        # If decoding is successful, maybe it is a text file
        try:
            text = elem.head_bytes.decode('utf-8')
        except UnicodeDecodeError:
            pass
        else:
            return False

        if elem.stat_size < 100*1024:
            return False

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
                
                try:
                    self._extract_to_dir(archive_path, temp_output_dir)
                except UnarException:
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
                        yield UnarElement(relative_path, fpath, scope=scope, parent_path=elem.qualpath)
            except FormatNotSupported:
                raise
            except Exception as exc:
                context.handle_unpacker_exception(exc=exc, elem=elem, logger=self.logger)

    def _subprocess_run(self, args, shell=False, timeout=None):
        import subprocess
        import sys
        if (sys.version_info.major, sys.version_info.minor) < (3, 7):
            if shell and isinstance(args, (list, tuple)):
                args = ' '.join(args)
            p = subprocess.Popen(args, shell=shell, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            try:
                outs, errs = p.communicate(timeout=timeout)
            except subprocess.TimeoutExpired:
                p.kill()
                outs, errs = p.communicate()
            return subprocess.CompletedProcess(args, returncode=p.returncode, stdout=outs, stderr=errs)
        else:
            if shell and isinstance(args, (list, tuple)):
                args = ' '.join(args)
            return subprocess.run(args, shell=shell, timeout=timeout, capture_output=True)

    def _extract_to_dir(self, input_file_path: str, output_dir: str):
        self.logger.debug('<extract_to_dir> extract "%s" to "%s"', input_file_path, output_dir)
        args = [
            self._unar_path,
            '-force-skip',
            '-encoding', 'utf-8'
            '-q',
            '-nr',
            '-o', output_dir,
            input_file_path,
        ]
        proc = self._subprocess_run(args, shell=False)
        stderr = proc.stderr.decode('utf-8') if proc.stderr else ''
        stdout = proc.stdout.decode('utf-8') if proc.stdout else ''
        # ignore returncode (any error) to support partial unpacking
        # 
        # if proc.returncode != 0:
        #     if "Couldn't recognize the archive format" in stderr:
        #         pass
        #     else:
        #         raise UnarException(f'unar command failed. returncode: {proc.returncode}\n{stderr}')
                