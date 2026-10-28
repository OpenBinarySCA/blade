import os
import traceback
from collections.abc import Iterable
from .exception import *
from .interface import *
from .log import *


class FileSystemElement(ExtractorElement):
    def __init__(self, filename, filepath, *, scope) -> None:
        super().__init__(scope=scope, parent_path=None)
        self._name = filename
        self._path = filepath
        with open(self._path, 'rb') as f:
            self._head_bytes = f.read(self.HEADER_BYTES_MAX)
        statinfo = os.stat(self._path)
        self._stat_size = statinfo.st_size
        self._stat_mtime = statinfo.st_mtime
        self._stat_mode = statinfo.st_mode

    def open_stream(self):
        return open(self._path, 'rb')

    @property
    def path_in_local_fs(self):
        return self._path

class ExtractorEngine(Engine):
    def __init__(self) -> None:
        super().__init__()
        self.logger = getLogger(self.__class__.__name__)
        self._unpackers:   typing.Mapping[str, Unpacker] = {}
        self._flexible_unpackers: typing.List[Unpacker]  = []
        self._wildcard_unpackers: typing.List[Unpacker]  = []
        self._bytesig_map:      typing.Mapping[int, tuple]      = {}
        self._config = {}
        self._temp_dir = None

    @property
    def temp_dir(self):
        return self._temp_dir

    def initialize(self, temp_dir=None) -> None:
        import tempfile
        if not temp_dir:
            temp_dir = tempfile.gettempdir()
        self._temp_dir = tempfile.mkdtemp(prefix='extractor-', dir=temp_dir)
        self.logger.debug('<initialize> temp_dir: %s', self._temp_dir)

        for class_entry in self.find_class_in_submodules( __package__ + '.unpackers', Unpacker ):
            try:
                instance = class_entry['class']()
                instance.initialize(self)
                self._unpackers[instance.name] = instance
                self.logger.debug(f'load {class_entry["class_qualname"]}')
            except Exception as exc:
                self.logger.warning(f'{class_entry["class_qualname"]} initialize failed. exc: {str(exc)}')

        for instance in list(self._unpackers.values()):
            signatures = instance.byte_signatures()
            if signatures == None:
                continue
            if signatures == BYTE_SIGNATURES_FLEXIBLE:
                self._flexible_unpackers.append(instance)     
                continue
            if signatures == BYTE_SIGNATURES_WILDCARD:
                self._wildcard_unpackers.append(instance) 
                continue               
            if isinstance(signatures, bytes):
                signatures = [signatures]
            if isinstance(signatures, (tuple, list)):
                for sig in signatures:
                    if not isinstance(sig, bytes):
                        self.logger.warn(f'unknown byte_signatures from {instance.name}: {type(sig)} {repr(sig)}')
                        continue
                    if sig[0] not in self._bytesig_map:
                        self._bytesig_map[sig[0]] = []
                    self._bytesig_map[sig[0]].append((sig, instance))
            else:
                self.logger.warn(f'unknown byte_signatures from {instance.name}: {type(signatures)} {repr(signatures)}')
        
        for _, instances in self._bytesig_map.items():
            instances: list
            instances.sort(key=lambda x:(x[1].priority, len(x[0])), reverse=True)
        self._flexible_unpackers.sort(key=lambda x:x.priority, reverse=True)
        self._wildcard_unpackers.sort(key=lambda x:x.priority, reverse=True)

    def deinitialize(self) -> None:
        for instance in self._unpackers.values():
            try:
                instance.deinitialize()
            except Exception:
                self.logger.warn(f'unhandled exception from {instance.name}.deinitialize\n{traceback.format_exc()}')
        if self._temp_dir:
            import shutil
            try:
                self.logger.debug(f'<deinitialize> delete temp_dir {self._temp_dir}')
                if os.path.exists(self._temp_dir):
                    shutil.rmtree(self._temp_dir)
            except OSError as exc:
                self.logger.warn(f'<deinitialize> delete tmp dir failed. {str(exc)}. path={self._temp_dir}')

    def config_get(self, name_or_path, default=None):
        path_components = name_or_path.split('.')
        obj = self._config
        for name in path_components:
            obj = obj.get(name)
            if obj is None:
                return default
        return obj
        
    def find_class_in_one_module(self, modulename, base_cls):
        import importlib
        from inspect import isclass
        class_list = []
        try:
            module = importlib.import_module(modulename)
        except ModuleNotFoundError as exc:
            self.logger.warning(f'<find_module> import "{modulename}" failed. {str(exc)}')
            return class_list
        except Exception as exc:
            self.logger.warning(f'<find_module> import "{modulename}" failed. \n{traceback.format_exc(limit=-1)}')
            return class_list

        for name in dir(module):
            if name.startswith('__'): continue
            value = getattr(module, name)
            if not isclass(value): continue
            #print(f'find_main_cls {modulename} {name} {type(value)} ')
            if (value != base_cls) and issubclass(value, base_cls):
                class_list.append((name, value))
        return class_list

    def find_class_in_submodules(self, package_qualname, base_cls):
        import importlib
        import inspect
        from .utils import list_submodules
        modules_pkg = importlib.import_module(package_qualname)
        module_names = list_submodules(modules_pkg, recursive=True)

        class_filepath_set = set()
        classes = []
        for submod_qualname in module_names:
            modulename = package_qualname + '.' + submod_qualname
            #self.logger.debug(f'submod_qualname {submod_qualname}')
            if ('cli_' in  submod_qualname) or ('__main__' in submod_qualname) or ('.cli' in submod_qualname) or ('._' in submod_qualname):
                continue
            for class_name, class_obj in self.find_class_in_one_module(modulename, base_cls):
                class_filepath = inspect.getmodule(class_obj)
                if (class_name,class_filepath) in class_filepath_set:
                    continue
                class_filepath_set.add((class_name,class_filepath))
               
                class_qualname = submod_qualname + '.' + class_name
                
                classes.append({
                    'class_qualname': class_qualname,
                    'class_name': class_name,
                    'class': class_obj,
                })
        return classes

    @classmethod
    def should_try_wildcard_unpackers(self, context: ExtractorContext, elem: ExtractorElement):
        if elem.filetype_obj:
            mime = elem.filetype_obj.mime
            if mime.startswith('audio') or mime.startswith('video'):
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

        if elem.stat_size < 10*1024:
            return False

        return True

    def bytes_to_hex(self, data):
        return ','.join('%02X'%b for b in data)

    def dispatch(self, context: ExtractorContext, elem: ExtractorElement):
        context.stats.inc_total()
        context.stats.inc_filetype(elem)

        # 过滤不接受输出的项
        if context.is_acceptable(elem):
            self.logger.debug(
                f'<dispatch> acceptable {elem.filetype_attrs}: {elem.qualpath}')
        else:
            self.logger.debug(
                f'<dispatch> filtered {elem.filetype_attrs}: {elem.qualpath}')
            context.stats.inc_filterd()
            return

        parent_yielded = False  # 父项是否已产出（防重复）

        # 不解包/层级限制：直接把父项作为未解包(False)产出
        if not context.should_unpack(elem):
            self.logger.debug(f'<dispatch> skip-unpack filtered {elem.filetype_attrs}: {elem.qualpath}')
            context.stats.inc_nounpack(elem)
            yield elem, False
            return

        if context.should_skip_nesting_unpack(elem):
            self.logger.debug(f'<dispatch> skip-nesting ({elem.scope.nesting_level}) {elem.qualpath}')
            context.stats.inc_nounpack(elem)
            yield elem, False
            return

        head_bytes = elem.head_bytes
        handler = None

        # bytesig -> flexible
        if head_bytes:
            bytes_sig_handlers = self._bytesig_map.get(head_bytes[0], None)
            if bytes_sig_handlers:
                for sig, instance in bytes_sig_handlers:
                    if head_bytes.startswith(sig) and instance.is_supported_format(context, elem, head_bytes):
                        handler = instance
                        break

        if not handler:
            self.logger.debug('<dispatch> handler not found')
            for instance in self._flexible_unpackers:
                if instance.is_supported_format(context, elem, head_bytes):
                    handler = instance
                    break

        def _yield_children(res):
            """产出子项；返回是否至少产出过一个子项"""
            produced = False
            if res is None:
                return False
            if isinstance(res, ExtractorElement):
                # 递归处理单个子元素
                for child, child_flag in self.dispatch(context, res):
                    produced = True
                    yield child, child_flag
                return produced
            if isinstance(res, Iterable):
                for child_elem in res:
                    # 递归处理每个子元素
                    for child, child_flag in self.dispatch(context, child_elem):
                        produced = True
                        yield child, child_flag
                return produced
            return False

        # ---- 尝试使用找到的 handler ----
        handler_succeeded = False  # 标记 handler 是否成功

        if handler:
            try:
                self.logger.debug(f'<dispatch> call {handler.name} {elem.qualpath}')
                result_or_iter = handler.extract(context, elem)

                # 先产出所有子项，并记录是否有子项
                has_children = False
                for out in _yield_children(result_or_iter):
                    # 一旦确认有子项，先产出父项（带 True 标记）
                    if not parent_yielded:
                        yield elem, True
                        parent_yielded = True
                        context.stats.inc_unpacked(elem, handler)
                    has_children = True
                    handler_succeeded = True  # 有子项说明成功了
                    yield out

                del result_or_iter

                # 即使没有子项，只要没抛异常也算成功
                if not has_children:
                    handler_succeeded = True

            except (FormatNotSupported, UnicodeDecodeError) as e:
                # 格式不支持或解码错误，重置 handler 以便尝试 wildcard
                self.logger.debug(
                    f'<dispatch> {handler.name} format error for {elem.qualpath}: {type(e).__name__}: {e}')
                handler = None
                handler_succeeded = False

            except KeyboardInterrupt:
                self.logger.debug(f'<dispatch> KeyboardInterrupt {elem.qualpath}')
                context.stop()
                raise ExtractorExit(f'reason=KeyboardInterrupt, qualpath={elem.qualpath}') from None
            except GeneratorExit:
                self.logger.debug(f'<dispatch> GeneratorExit {elem.qualpath}')
                context.stop()
                raise ExtractorExit(f'reason=GeneratorExit, qualpath={elem.qualpath}') from None
            except ExtractorExit:
                self.logger.debug(f'<dispatch> ExtractorExit {elem.qualpath}')
                raise
            except Exception as exc:
                if context.is_passable_exception(exc):
                    raise
                self.logger.warning(
                    f'<dispatch> Unhandled exception while process {elem.qualpath}\n{traceback.format_exc()}')
                if not context.ignore_error:
                    raise
                # 如果 ignore_error=True，也重置 handler 以便尝试 wildcard
                handler = None
                handler_succeeded = False

        # ---- 无 handler 或 handler 失败 → wildcard 尝试 ----
        if not handler_succeeded and self.should_try_wildcard_unpackers(context, elem):
            for h in self._wildcard_unpackers:
                try:
                    if not h.is_supported_format(context, elem, head_bytes):
                        raise FormatNotSupported()
                    self.logger.debug(f'<dispatch> try {h.name} {elem.qualpath}')
                    result_or_iter = h.extract(context, elem)

                    has_children = False
                    for out in _yield_children(result_or_iter):
                        # 一旦确认有子项，先产出父项（带 True 标记）
                        if not parent_yielded:
                            yield elem, True
                            parent_yielded = True
                            context.stats.inc_unpacked(elem, h)
                        has_children = True
                        yield out

                    del result_or_iter

                    if has_children:
                        handler_succeeded = True
                        break  # 成功就停

                except FormatNotSupported:
                    continue
                except KeyboardInterrupt:
                    self.logger.debug(f'<dispatch> KeyboardInterrupt {elem.qualpath}')
                    context.stop()
                    raise ExtractorExit(f'reason=KeyboardInterrupt, qualpath={elem.qualpath}') from None
                except GeneratorExit:
                    self.logger.debug(f'<dispatch> GeneratorExit {elem.qualpath}')
                    context.stop()
                    raise ExtractorExit(f'reason=GeneratorExit, qualpath={elem.qualpath}') from None
                except ExtractorExit:
                    self.logger.debug(f'<dispatch> ExtractorExit {elem.qualpath}')
                    raise
                except Exception as exc:
                    if context.is_passable_exception(exc):
                        raise
                    self.logger.warning(
                        f'<dispatch> Unhandled exception while process {elem.qualpath}\n{traceback.format_exc()}')
                    if not context.ignore_error:
                        raise

        # ---- 收尾：若父项尚未产出，补一次 False（未解压） ----
        if not parent_yielded:
            if not handler_succeeded:
                self.logger.debug(f'<dispatch> This file cannot be unpacked: {elem.qualpath}')
            context.stats.inc_nounpack(elem)
            yield elem, False

    def _scan_file(self, context: ExtractorContext, scope: ExtractorScope, fpath: str, fname=None):
        import stat
        import os
        if not fname:
            fname = os.path.basename(fpath)
        file_stat = os.stat(fpath, follow_symlinks=False)
        if stat.S_ISREG(file_stat.st_mode):
            yield from self.dispatch(context, FileSystemElement(fname, fpath, scope=scope))
                    
    def _scan_dir(self, context: ExtractorContext, scope: ExtractorScope, dirpath: str):
        root_path = os.path.normpath(dirpath)
        for root, dirs, files in os.walk(root_path):
            if context.is_stoping: 
                break
            for fname in files:
                fpath = os.path.join(root, fname)
                relative_path = fpath[len(root_path)+1:]
                yield from self._scan_file(context, scope, fpath, fname)

    def extract(self, path: str, stats=None, **options) -> typing.Iterable[ExtractorElement]:
        self.logger.debug(f'<extract> path: {path}')
        self.logger.debug(f'<extract> options: \n' + "\n".join("{:>20} = {}".format(k, v) for k, v in options.items()))
        
        context = ExtractorContext(engine=self, options=options)
        try:
            with ExtractorScope(unpacker=None, context=context, elem=None) as scope:
                try:
                    if os.path.isdir(path):
                        yield from self._scan_dir(context, scope, path)
                    else:
                        yield from self._scan_file(context, scope, path)
                except ExtractorExit:
                    self.logger.debug(f'<extract> ExtractorExit {path}')
        finally:
            if stats != None:
                stats.update(context.stats.copy())
            self.logger.info(f'<extract> statistics: \n{context.stats.dump()}')