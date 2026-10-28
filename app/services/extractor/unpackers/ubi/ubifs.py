import os

from ...interface import *
from ...log import *

class UBIFSElement(LocalFileSystemElementImpl):
    pass

class UBIFSUnpacker(Unpacker):
    logger = getLogger('UBIFSUnpacker')

    def initialize(self, engine: Engine) -> None:
        super().initialize(engine)
        from ubireader.ubi import ubi
        from ubireader.ubi_io import ubi_file, leb_virtual_file
        from ubireader.ubifs import ubifs
        from ubireader.ubifs.output import extract_files
        from ubireader.utils import guess_filetype, guess_start_offset, guess_peb_size, guess_leb_size
        
    @property
    def name(self) -> str:
        return 'UBIFSUnpacker'
        
    def byte_signatures(self):
        return b'\x31\x18\x10\x06'

    def is_supported_format(self, context: ExtractorContext, elem: ExtractorElement, head_bytes: bytes) -> bool:
        return head_bytes.startswith(b'\x31\x18\x10\x06')

    def extract(self, context: ExtractorContext, elem: ExtractorElement):
        import stat
        from ...utils import copy_stream_to_file

        with ExtractorScope(unpacker=self, context=context, elem=elem) as scope:
            try:
                temp_dir = scope.temp_dir
                temp_input_file = os.path.join(temp_dir, 'img.ubifs')
                temp_output_dir = os.path.join(temp_dir, 'output')
                os.mkdir(temp_output_dir)
                with elem.open_stream() as stream:
                    copy_stream_to_file(stream, temp_input_file)
                
                self._extract_to_dir(temp_input_file, temp_output_dir)
                root_path = temp_output_dir
                for root, dirs, files in os.walk(root_path):
                    for fname in files:
                        fpath = os.path.join(root, fname)
                        relative_path = fpath[len(root_path)+1:]
                        file_stat = os.stat(fpath, follow_symlinks=False)
                        if not stat.S_ISREG(file_stat.st_mode):
                            if stat.S_ISLNK(file_stat.st_mode):
                                context.stats.inc_symlink()
                            continue
                        yield UBIFSElement(relative_path, fpath, scope=scope, parent_path=elem.qualpath)
            except Exception as exc:
                context.handle_unpacker_exception(exc=exc, elem=elem, logger=self.logger)
    
    def _extract_to_dir(self, path, output_dir):
        from ubireader.ubi import ubi
        from ubireader.ubi_io import ubi_file, leb_virtual_file
        from ubireader.ubifs import ubifs
        from ubireader.ubifs.output import extract_files
        from ubireader.utils import guess_filetype, guess_start_offset, guess_peb_size, guess_leb_size
        block_size = guess_leb_size(path)
        start_offset = guess_start_offset(path)
        end_offset = None
        # Create file object.
        ufile_obj = ubi_file(path, block_size, start_offset, end_offset)
        
        # Create UBIFS object
        ubifs_obj = ubifs(ufile_obj)

        # Extract files from UBIFS image.
        with RedirectOutputToLogger(self.logger):
            extract_files(ubifs_obj, output_dir, perms=True)

class RedirectOutputToLogger:
    def __init__(self, logger) -> None:
        self.logger = logger
        from ubireader import debug
        self._debug_mod = debug
        self._old_values = {}
        self._stubs = {}
        self._instance_var_name = f'_instance_{id(self)}'
        self._funcs_to_hook = [
            # 'log', 
            # 'verbose_log', 
            # 'verbose_display', 
            'error',
        ]

    def __enter__(self):
        for name in self._funcs_to_hook:
            new_func = self.make_stub(self._instance_var_name, name)
            self._stubs[name] = new_func
            func = getattr(self._debug_mod, name, None)
            if func != None:
                value = getattr(func, '__code__', None)
                if value != None:
                    self._old_values[name] = value
                    setattr(func, '__code__', new_func.__code__)
                    func.__globals__[self._instance_var_name] = self
        return self

    def __exit__(self, type, value, trace):
        for name in list(self._old_values.keys()):
            new_func = self._stubs[name]
            func = getattr(self._debug_mod, name, None)
            if func != None:
                value = getattr(func, '__code__', None)
                if value == new_func.__code__:
                    setattr(func, '__code__', self._old_values[name])
                    del func.__globals__[self._instance_var_name]
                else:
                    self.logger.debug(f'<RedirectOutputToLogger> {name} not hooked')
            
    def make_stub(self, instance_var_name, method_name):
        stub_name = f"_stub_{instance_var_name}_{method_name}"
        text = (
            f"def {stub_name}(*args, **kwargs):\n"
            f"    return {instance_var_name}.{method_name}(*args, **kwargs)\n"
        )
        vars = {}
        exec(text, vars, vars)
        return vars[stub_name]

    def log(self, obj, message):
        self.logger.debug('<log> ' + '{} {}'.format(obj.__name__, message))

    def verbose_log(self, obj, message):
        self.logger.debug('<verbose_log> ' + '{} {}'.format(obj.__name__, message))

    def verbose_display(self, displayable_obj):
        self.logger.debug('<verbose_display> ' + displayable_obj.display('\t') )

    def error(self, obj, level, message):
        self.logger.debug('<error> ' + '{} {}: {}'.format(obj.__name__, level, message))
