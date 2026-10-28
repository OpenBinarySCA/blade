import os

from ..interface import *
from ..log import *

class ISOElement(ExtractorElement):
    def __init__(self, isofile, path, raw_path, node, *, scope, parent_path) -> None:
        super().__init__(scope=scope, parent_path=parent_path)
        self._isofile = isofile
        self._raw_path = raw_path
        self._node = node
        self._name = os.path.split(path)[1]
        self._path = path
        with self._isofile.open_file_from_iso(**self._raw_path) as f:
            self._head_bytes = f.read(self.HEADER_BYTES_MAX)

        self._stat_size = self._node.data_length
        self._stat_mtime = 0
        self._stat_mode = 0
        self._buf = None
        
    def open_stream(self):
        f = self._isofile.open_file_from_iso(**self._raw_path)
        f.__enter__()
        return self.StreamWrapper(
            self,
            f,
        )

class ISOUnpacker(Unpacker):
    logger = getLogger('ISOUnpacker')
    @property
    def name(self) -> str:
        return 'ISOUnpacker'
        
    def initialize(self, engine: Engine) -> None:
        super().initialize(engine)
        import pycdlib
       
    @property
    def priority(self):
        return 10

    def byte_signatures(self):
        return BYTE_SIGNATURES_FLEXIBLE

    def is_supported_format(self, context: ExtractorContext, elem: ExtractorElement, head_bytes: bytes) -> bool:
        import pycdlib
        import pycdlib.pycdlibexception

        isofile = pycdlib.PyCdlib()
        if (elem.stat_size < 1024*1024*1) or (elem.filetype != elem.FILETYPE_UNKNOWN):
            return False
        with elem.open_stream() as stream:
            try:
                isofile.open_fp(stream)
            except pycdlib.pycdlibexception.PyCdlibException as exc:
                return False
            except EOFError as exc:
                return False
        return True

    def extract(self, context: ExtractorContext, elem: ExtractorElement):
        import pycdlib
        import pycdlib.pycdlibexception

        isofile = pycdlib.PyCdlib()
        with ExtractorScope(unpacker=self, context=context, elem=elem) as scope:
            try:
                with elem.open_stream() as stream:
                    isofile.open_fp(stream)
                    for path, raw_path, node in self._walk_tree(isofile):
                        if scope.should_skip:
                            break
                        try:
                            with isofile.open_file_from_iso(**raw_path) as f:
                                pass
                        except pycdlib.pycdlibexception.PyCdlibException as exc:
                            self.logger.info(f'<extract> error. qualpath: {elem.qualpath},  path: {path}, exc: {str(exc)}')
                            continue
                        yield ISOElement(isofile, path, raw_path, node, scope=scope, parent_path=elem.qualpath)
            except Exception as exc:
                context.handle_unpacker_exception(exc=exc, elem=elem, logger=self.logger)

    def _walk_tree(self, iso):
        import collections
        if iso.has_udf():
            pathname = 'udf_path'
        elif iso.has_rock_ridge():
            pathname = 'rr_path'
        elif iso.has_joliet():
            pathname = 'joliet_path'
        else:
            pathname = 'iso_path'
        
        root_path = '/'
        root_entry = iso.get_record(**{pathname: root_path})

        dirs = collections.deque([root_entry])
        while dirs:
            dir_record = dirs.popleft()
            ident_to_here = iso.full_path_from_dirrecord(dir_record,
                                                        rockridge=pathname == 'rr_path')
            relname = ident_to_here[len(root_path):]
            if relname and relname[0] == '/':
                relname = relname[1:]
            print(relname)
            if dir_record.is_dir():
                child_lister = iso.list_children(**{pathname: ident_to_here})
                for child in child_lister:
                    if child is None or child.is_dot() or child.is_dotdot():
                        continue
                    dirs.append(child)
            else:
                if dir_record.is_symlink():
                    symlink_path = dir_record.rock_ridge.symlink_path()
                else:
                    yield relname, {pathname: ident_to_here}, iso.get_record(**{pathname: ident_to_here})
