import os

from ..exception import FormatNotSupported
from ..interface import *
from ..log import *
from ..utils import copy_stream_to_file


class BinwalkException(Exception):
    pass


class BinwalkElement(LocalFileSystemElementImpl):
    pass


class BinwalkWrapper(Unpacker):
    logger = getLogger('BinwalkWrapper')
    _binwalk_available = False

    def initialize(self, engine: Engine) -> None:
        super().initialize(engine)
        try:
            import binwalk
            self._binwalk_available = True
        except ImportError:
            self.logger.warning('binwalk module not available')

    @property
    def name(self) -> str:
        return 'BinwalkWrapper'

    @property
    def priority(self):
        return -1

    def byte_signatures(self):
        return BYTE_SIGNATURES_WILDCARD

    def is_supported_format(self, context: ExtractorContext, elem: ExtractorElement, head_bytes: bytes) -> bool:
        if context.current_unpacker() == self.name:
            self.logger.debug('<is_supported_format> parent unpacker is binwalk, reject')
            return False

        # offset = elem.name.rfind('.')
        # if offset >= 0:
        #     ext_name = elem.name[offset:]
        # else:
        #     ext_name = ''
        #
        # if ext_name.lower() not in ('', '.bin', '.img'):
        #     return False

        if elem.filetype_obj:
            mime = elem.filetype_obj.mime
            if mime.startswith('audio') or mime.startswith('video') or mime.startswith('image'):
                return False
            if elem.filetype_obj.extension.lower() in ('elf',):
                return False

        # If decoding is successful, maybe it is a text file
        try:
            text = elem.head_bytes.decode('utf-8')
        except UnicodeDecodeError:
            pass
        else:
            return False

        if elem.stat_size < 1024 * 1024:
            return False
        if elem.stat_size >= 1024 * 1024 * 100:
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
                    temp_output_dir = self._extract_to_dir(archive_path, temp_output_dir)
                except BinwalkException:
                    # traceback.print_exc()
                    raise FormatNotSupported() from None
                if not os.path.exists(temp_output_dir):
                    raise FormatNotSupported()
                if len(list(os.listdir(temp_output_dir))) == 0:
                    raise FormatNotSupported()
                root_path = os.path.normpath(temp_output_dir)
                for root, dirs, files in os.walk(root_path):
                    for fname in files:
                        fpath = os.path.join(root, fname)
                        relative_path = fpath[len(root_path) + 1:]
                        file_stat = os.stat(fpath, follow_symlinks=False)
                        if not stat.S_ISREG(file_stat.st_mode):
                            if stat.S_ISLNK(file_stat.st_mode):
                                context.stats.inc_symlink()
                            continue
                        yield BinwalkElement(relative_path, fpath, scope=scope, parent_path=elem.qualpath)
            except FormatNotSupported:
                raise
            except Exception as exc:
                context.handle_unpacker_exception(exc=exc, elem=elem, logger=self.logger)

    def _extract_to_dir(self, input_file_path: str, output_dir: str):
        import sys
        import subprocess
        args = [
            sys.executable,
            '-m', 'binwalk',
            '-e',
            '--run-as=root',
            '-z',
            f'--directory={output_dir}',
            input_file_path
        ]

        proc = subprocess.run(args, shell=False, capture_output=True, timeout=300)  # 添加超时
        stderr = proc.stderr.decode('utf-8', errors='replace') if proc.stderr else ''
        stdout = proc.stdout.decode('utf-8', errors='replace') if proc.stdout else ''

        if proc.returncode != 0:
            raise BinwalkException(f'command failed. returncode: {proc.returncode}\n{stderr}')
        for name in os.listdir(output_dir):
            if name.endswith('.extracted'):
                extracted_path = os.path.join(output_dir, name)
                if os.path.isdir(extracted_path):
                    return extracted_path
        raise BinwalkException('Unexpected output dir layout')
