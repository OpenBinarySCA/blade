import os
import struct
import typing
import traceback
import weakref
from .element import ExtractorElement
from .exception import *

class ExtractorContext:
    def __init__(self, *, engine, options) -> None:
        self._engine_ref = weakref.ref(engine)
        self._options = options if options else {}
        self._bytesigs_map: typing.Mapping[int, bytes]  = {}
        self._no_bytesigs = False
        self._filetypes = set()
        self._no_filetypes = False
        self._ignore_error = self._options.get('ignore_error', False)
        self._is_stoping = False
        self._unpacker_chain = []
        self._nounpack_filetypes = self._options.get('nounpack_filetypes', None)
        self._output_filetypes = self._options.get('output_filetypes', None)
        self._stats = Statistics()
        self._max_nesting_level = self._options.get('max_nesting_level') or -1
        self._load_bytesigs_and_filetypes()
        self._output_filter = self._options.get('output_filter')
        self._unpack_filter = self._options.get('unpack_filter')

    def _load_bytesigs_and_filetypes(self):
        bytesigs = self._options.get('bytesigs')
        filetypes = self._options.get('filetypes')
        if (bytesigs == None) or (len(bytesigs) == 0) :
            self._no_bytesigs = True
        else:
            if isinstance(bytesigs, bytes):
                bytesigs = [bytesigs]
            if isinstance(bytesigs, (tuple, list)):
                for sig in bytesigs:
                    if sig[0] not in self._bytesigs_map:
                        self._bytesigs_map[sig[0]] = []
                    self._bytesigs_map[sig[0]].append(sig)
            else:
                raise ValueError(f'sigs should be None, bytes or list of bytes. got: {type(bytesigs)} {repr(bytesigs)}')

        if (filetypes == None) or (len(filetypes) == 0) :
            self._no_filetypes = True
        else:
            if isinstance(filetypes, str):
                filetypes = [filetypes]
            if isinstance(filetypes, (tuple, list)):
                pass
            else:
                raise ValueError(f'sigs should be None, bytes or list of bytes. got: {type(bytesigs)} {repr(bytesigs)}')
            self._filetypes = set([x.lower() for x in filetypes])

    def is_acceptable(self, elem: ExtractorElement):
        # if self._output_filter:
        #     return bool(self._output_filter(elem))
        #
        # if self._no_bytesigs and self._no_filetypes:
        #     return True
        #
        # head_bytes = elem.head_bytes
        # if len(head_bytes) > 0:
        #     sigs_group = self._bytesigs_map.get(head_bytes[0], None)
        #     if sigs_group:
        #         for sig in sigs_group:
        #             if head_bytes.startswith(sig):
        #                 return True
        #
        # if elem.filetype in self._filetypes:
        #     return True
        # return False

        if self._output_filetypes:
            if 'mime_types' in self._output_filetypes:
                mime_types = self._output_filetypes['mime_types']
                if elem.filetype_attrs['mime_type'] in mime_types:
                    return False
            if 'ext_names' in self._output_filetypes:
                ext_names = self._output_filetypes['ext_names']
                if os.path.splitext(str(elem.qualpath))[1].lower().lstrip('.') in ext_names:
                    return False
            if 'charsets' in self._output_filetypes:
                charsets = self._output_filetypes['charsets']
                if elem.filetype_attrs['charset'] not in charsets:
                    return False
            if '__MACOSX' in elem.path:
                return False
        return True
    
    def should_unpack(self, elem: ExtractorElement):
        # if self._unpack_filter:
        #     return bool(self._unpack_filter(elem))

        if self._nounpack_filetypes:
            if 'mime_types' in self._nounpack_filetypes:
                mime_types = self._nounpack_filetypes['mime_types']
                if elem.filetype_attrs['mime_type'] in mime_types:
                    return False
            if 'ext_names' in self._nounpack_filetypes:
                ext_names = self._nounpack_filetypes['ext_names']
                if os.path.splitext(str(elem.qualpath))[1].lower().lstrip('.') in ext_names:
                    return False
            if 'charsets' in self._nounpack_filetypes:
                charsets = self._nounpack_filetypes['charsets']
                if elem.filetype_attrs['charset'] not in charsets:
                    return False
        return True

    def should_skip_nesting_unpack(self, elem: ExtractorElement):
        if self._max_nesting_level > 0:
            if elem.scope.nesting_level >= self._max_nesting_level:
                return True
        return False

    @property
    def ignore_error(self):
        return self._ignore_error

    @property
    def options(self):
        return self._options

    @property
    def temp_dir(self):
        engine = self._engine_ref()
        if engine:
            return engine.temp_dir
        else:
            return None

    @property
    def stats(self):
        return self._stats

    @property
    def is_stoping(self):
        return self._is_stoping

    def stop(self):
        self._is_stoping = True

    def is_passable_exception(self, exc):
        return isinstance(exc, ExtractorExit)

    def handle_unpacker_exception(self, *, exc:Exception, elem: ExtractorElement, logger):
        if self.is_passable_exception(exc):
            raise

        # ✅ 对于格式错误，转换为 FormatNotSupported
        if isinstance(exc, (UnicodeDecodeError, struct.error, ValueError)):
            logger.debug(f'<extract> format error. {str(exc)}. qualpath={elem.qualpath}.')
            raise FormatNotSupported(f"Format parse error: {exc}") from exc

        if not self.ignore_error:
            raise
        logger.debug(f'<extract> ignore error. {str(exc)}. qualpath={elem.qualpath}.\n{traceback.format_exc()}')
        self.stats.inc_ignored_error()

    def enter_unpacker(self, name):
        self._unpacker_chain.append(name)

    def leave_unpacker(self, name):
        if self._unpacker_chain[-1] == name:
            self._unpacker_chain.pop(-1)
        else:
            pass
    
    def current_unpacker(self):
        return self._unpacker_chain[-1]

class Statistics:
    def __init__(self) -> None:
        import collections
        self._data = {
            'symlink': 0,
            'total': 0,
            'filterd': 0,
            'unpacked': 0,
            'nounpack': 0,
            'error': 0,
            'by_filetype': collections.defaultdict(int),
            'by_unpacker': collections.defaultdict(int)
        }

    def inc_symlink(self):
        self._data['symlink'] += 1
    
    def inc_statmode(self, mode):
        """
            0170000  This masks the file type bits.
            0140000  File type value for sockets.
            0120000  File type value for symbolic links.  For symbolic links, the link body is
                    stored as file data.
            0100000  File type value for regular files.
            0060000  File type value for block special devices.
            0040000  File type value for directories.
            0020000  File type value for character special devices.
            0010000  File type value for named pipes or FIFOs.
        """
        pass 
    
    def inc_total(self):
        self._data['total'] += 1
    
    def inc_filterd(self):
        self._data['filterd'] += 1

    def inc_ignored_error(self):
        self._data['error'] += 1
    
    def inc_filetype(self, elem: ExtractorElement):
        self._data['by_filetype'][elem.filetype] += 1

    def inc_unpacked(self, elem: ExtractorElement, unpacker):
        self._data['unpacked'] += 1
        self._data['by_unpacker'][unpacker.name] += 1

    def inc_nounpack(self, elem: ExtractorElement):
        self._data['nounpack'] += 1
    
    def copy(self):
        m = dict(self._data)
        m['by_unpacker'] = dict(self._data['by_unpacker'])
        m['by_filetype'] = dict(self._data['by_filetype'])
        return m

    def dump(self):
        lines = (
            f"{'-'*40}\n"
            f"{'error':>20}: {self._data['error']}\n"
            f"{'-'*40}\n"
            f"{'symlink':>20}: {self._data['symlink']}\n"
            f"{'total':>20}: {self._data['total']}\n"
            f"{'filterd':>20}: {self._data['filterd']}\n"
            f"{'unpacked':>20}: {self._data['unpacked']}\n"
            f"{'nounpack':>20}: {self._data['nounpack']}\n"
        )
        
        for ftype, value in self._data['by_filetype'].items():
            lines += (
                f"{ftype:>20}: {value}\n"
            )
        lines += f"{'-'*40}\n"
        for unpacker, value in self._data['by_unpacker'].items():
            lines += (
                f"{unpacker:>20}: {value}\n"
            )
        lines += f"{'-'*40}\n"
        return lines
