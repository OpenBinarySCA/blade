import os

from ....interface import *
from ....log import *
from ....utils import copy_stream_to_file


class AndroidBootImageElement(LocalFileSystemElementImpl):
    pass

class AndroidBootImageUnpacker(Unpacker):
    logger = getLogger('AndroidBootImageUnpacker')

    def initialize(self, engine: Engine) -> None:
        super().initialize(engine)

    @property
    def name(self) -> str:
        return 'AndroidBootImageUnpacker'

    @property
    def priority(self):
        return -1
        
    def byte_signatures(self):
        return b'ANDROID!'

    def is_supported_format(self, context: ExtractorContext, elem: ExtractorElement, head_bytes: bytes) -> bool:
        return head_bytes.startswith(b'ANDROID!')

    def extract(self, context: ExtractorContext, elem: ExtractorElement):

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
                        yield AndroidBootImageElement(relative_path, fpath, scope=scope, parent_path=elem.qualpath)
            except Exception as exc:
                context.handle_unpacker_exception(exc=exc, elem=elem, logger=self.logger)

    def _extract_to_dir(self, input_file_path: str, output_dir: str):
        from . import unpack_bootimg
        texts = []
        def hacked_print(*args, **kwargs):
            info = ''.join([str(x) for x in args])
            texts.append(info)
        unpack_bootimg.print = hacked_print
        class Args:
            pass
        with open(input_file_path, 'rb') as img_f:
            args = Args()
            args.boot_img = img_f
            args.out = output_dir
            unpack_bootimg.unpack_bootimage(args)
        with open(os.path.join(output_dir, 'bootimg.cfg'), 'wb+') as f:
            f.write('\n'.join(texts).encode('utf-8'))

            
