import os
import shutil
import argparse
import time
import traceback
import hashlib

from . import extract_iter
from .constants import nounpack_filetypes, output_filetypes

print('__package__', __package__)


# def assure_filename_valid(path):
#     import os
#     import binascii
#     parts = path.split('/')
#     new = []
#     for p in parts:
#         x = re.sub('[^A-Za-z0-9\\._\\-\\[\\]]', '-', p)
#         x = x + '.' + binascii.b2a_hex(os.urandom(4))
#         new.

class FileList:
    def __init__(self, filename, filepath) -> None:
        self.original_file_sha1 = None
        self.original_file_md5 = None
        self._filepath = filepath
        self.files = []
        self.original_filename = filename
        self.original_mime_type = None
        self.original_readable_type = None
        self.original_file_size = None

    def save(self):
        import json
        with open(self._filepath, 'w+') as f:
            json.dump(obj=self.files, fp=f, indent=1)

    def __str__(self) -> str:
        lines = [
            f"FileList: {self._filepath}",
            f"Total files: {len(self.files)}",
            "=" * 80
        ]

        # 显示原始文件信息
        if self.original_filename:
            lines.append("Original File Information:")
            lines.append(f"  Filename: {self.original_filename}")
            if self.original_file_size is not None:
                lines.append(f"  Size: {round(self.original_file_size / (1024 * 1024), 3)} MB")
            if self.original_readable_type:
                lines.append(f"  Type: {self.original_readable_type}")
            if self.original_mime_type:
                lines.append(f"  MIME Type: {self.original_mime_type}")
            if self.original_file_sha1:
                lines.append(f"  SHA1: {self.original_file_sha1}")
            if self.original_file_md5:
                lines.append(f"  MD5: {self.original_file_md5}")
            lines.append("=" * 80)

        # 显示文件列表
        if self.files:
            lines.append("Files:")
        for i, entry in enumerate(self.files, 1):
            lines.append(f"{i}. {entry.get('filename', 'N/A')}")
            lines.append(f"   Size: {round(entry.get('filesize', 0) / (1024 * 1024), 3)} MB")
            lines.append(f"   Absolute path: {entry.get('absolute_path', 'N/A')}")
            if entry.get('relative_path'):
                lines.append(f"   Relative path: {entry.get('relative_path')}")
            if entry.get('readable_type'):
                lines.append(f"   Type: {entry['readable_type']}")
            if entry.get('mimetype'):
                lines.append(f"   MIME Type: {entry['mime_type']}")
            lines.append(f"   SHA1: {entry['sha1']}")
            lines.append(f"   MD5: {entry['md5']}")
            if i < len(self.files):
                lines.append("")

        return '\n'.join(lines)

    def to_list(self) -> list:
        """将 FileList 对象转换为列表格式"""
        result = []

        for entry in self.files:
            file_info = {
                'filename': entry.get('filename'),
                'filesize': entry.get('filesize'),
                'mime_type': entry.get('mime_type'),
                'readable_type': entry.get('readable_type'),
                # 'absolute_path': entry.get('absolute_path'),
                'relative_path': entry.get('relative_path'),
                'sha1': entry.get('sha1'),
                'md5': entry.get('md5')
            }
            result.append(file_info)

        return result


class HashCalculator:
    def __init__(self, md5=False, sha1=False) -> None:
        self._md5 = hashlib.md5() if md5 else None
        self._sha1 = hashlib.sha1() if sha1 else None

    def update(self, data: bytes):
        if self._md5:
            self._md5.update(data)
        if self._sha1:
            self._sha1.update(data)

    def final(self):
        pass

    def md5(self):
        return self._md5.hexdigest() if self._md5 else None

    def sha1(self):
        return self._sha1.hexdigest() if self._sha1 else None


def copy_stream_to_file(stream, filepath, hash_calc):
    with open(filepath, 'wb+') as f:
        while True:
            buf = stream.read(1024 * 1024)
            if len(buf) == 0:
                break
            f.write(buf)
            if hash_calc:
                hash_calc.update(buf)


def do_extract(*,
               input_path,
               output_dir,
               filetypes = None,
               fileexts = None,
               filelist_path=None,
               calc_md5=False,
               calc_sha1=False,
               dry_run=False,
               del_unpacked=True,
               use_fileter=True,
               ):
    # import logging
    # if not logfile:
    #     logging.basicConfig(level=logging.INFO)
    # else:
    #     LOGGING_CONFIG['handlers']['extractor_filelog']['filename'] = logfile
    #     import logging.config
    #     logging.config.dictConfig(LOGGING_CONFIG)
    # logger = logging.getLogger('do_extract')
    input_path = os.path.normpath(input_path)

    if not dry_run:
        if not os.path.exists(output_dir):
            try:
                os.mkdir(output_dir)
            except Exception as exc:
                print(f'Error: {str(exc)}')
                return None
        temp_dir = os.path.join(output_dir, '.extractor-tmp')
        if os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
            except Exception as exc:
                print(f'Error: Can not clear temp dir: {temp_dir}. {str(exc)}')
                return None
    else:
        import tempfile
        temp_dir = os.path.join(tempfile.gettempdir(), '.extractor-tmp')
    print(f'temp_dir {temp_dir}')
    os.mkdir(temp_dir)

    filelist = FileList(os.path.basename(input_path), filelist_path) if filelist_path else None

    if filetypes:
        filetypes = set(filetypes)
    if fileexts:
        fileexts = set([x.lower().strip('.') for x in fileexts])
    t0 = time.time()
    total_file_count = 0
    total_file_size = 0
    try:
        for item, success in extract_iter(input_path, temp_dir=temp_dir, ignore_error=True,
                                          nounpack_filetypes=nounpack_filetypes if use_fileter else None,
                                          output_filetypes=output_filetypes if use_fileter else None
                                          ):
            original_file = False
            if str(item.qualpath) == input_path:
                original_file = True
            try:
                if filetypes:
                    if item.filetype not in filetypes:
                        continue
                if fileexts:
                    ext = os.path.splitext(item.name)[1].lower().strip('.')
                    if ext not in fileexts:
                        continue
                total_file_count += 1
                total_file_size += item.stat_size
                relative_qualpath = str(item.qualpath)[len(input_path):]
                relative_qualpath = relative_qualpath.lstrip(':')
                relative_qualpath = relative_qualpath.replace('\\', '/')
                relative_qualpath = relative_qualpath.lstrip('/')
                parts = relative_qualpath.split(':')
                parts = [os.path.normpath(p).replace('\\', '/') for p in parts]
                parts = [p.lstrip('/') for p in parts if len(p.lstrip('/')) > 0]
                relative_realpath = '.xx_/'.join(parts)

                hash_calc = HashCalculator(md5=calc_md5, sha1=calc_sha1)

                if not original_file:
                    if not dry_run:
                        # logger.debug(f'output {relative_qualpath}')
                        try:
                            dest_path = os.path.join(output_dir, relative_realpath)
                            parent_dir = os.path.dirname(dest_path)
                            if not os.path.exists(parent_dir):
                                os.makedirs(parent_dir)
                            with item.open_stream() as f:
                                copy_stream_to_file(f, dest_path, hash_calc)

                        except:
                            print(f'Unhandled exception. {str(item.qualpath)}\n{traceback.format_exc()}')
                    else:
                        mime = item.filetype_obj.mime if item.filetype_obj else ''
                        # logger.debug(f'output "{mime}"  {relative_qualpath}')

                    hash_calc.final()
                abs_path = input_path if original_file else dest_path
                filesize = os.path.getsize(abs_path)
                if filelist:
                    if original_file:
                        filelist.original_filename = os.path.basename(input_path)
                        filelist.original_file_size = filesize
                        filelist.original_readable_type = item.filetype_attrs['readable_type'] if item.filetype_attrs else None
                        filelist.original_mime_type = item.filetype_attrs['mime_type'] if item.filetype_attrs else None
                        filelist.original_file_md5 = hash_calc.md5()
                        filelist.original_file_sha1 = hash_calc.sha1()

                    # 如果success为True，删除文件
                    if not original_file and del_unpacked and success and os.path.isfile(abs_path):
                        os.remove(abs_path)
                        continue

                    if not original_file or (original_file and not success):
                        filelist.files.append({
                            'filename': os.path.basename(relative_realpath) if not original_file else os.path.basename(
                                input_path),
                            'filesize': filesize,
                            'mime_type': item.filetype_attrs['mime_type'] if item.filetype_attrs else None,
                            'readable_type': item.filetype_attrs['readable_type'] if item.filetype_attrs else None,
                            'absolute_path': abs_path,
                            'relative_path': relative_realpath if not original_file else None,
                            'sha1': hash_calc.sha1(),
                            'md5': hash_calc.md5(),
                        })


            finally:
                del item
    finally:
        try:
            shutil.rmtree(temp_dir)
        except:
            pass
    t = time.time() - t0
    hours, remainder = divmod(t, 3600)
    minutes, seconds = divmod(remainder, 60)
    print(f'Total time: {int(hours)}:{int(minutes):02}:{int(seconds):02}')
    print(f'Total file count: {total_file_count}')
    print(f'Total file fize: {total_file_size / (1024 * 1024):.2f}M')
    if filelist:
        filelist.save()

    return filelist


def main():
    parser = argparse.ArgumentParser(__package__)
    parser.add_argument('-i', '--input', help='file/dir to extract')
    parser.add_argument('--filetype', nargs='*', help='file types to extract')
    parser.add_argument('--fileext', nargs='*', help='file exts to extract')
    parser.add_argument('-o', '--output', required=True, help='output dir. "-" means dry-run')
    parser.add_argument('--logfile', help='extractor logfile')
    parser.add_argument('--filelist', help='list of extracted files')
    parser.add_argument('--calc-md5', dest='calc_md5', action='store_true', default=False,
                        help='output md5 in filelist')
    parser.add_argument('--calc-sha1', dest='calc_sha1', action='store_true', default=False,
                        help='output sha1 in filelist')
    parser.add_argument('--tempdir', help='tempdir')
    parsed_arg = parser.parse_args()
    path = parsed_arg.input
    if not os.path.isabs(path):
        path = os.path.abspath(path)
    path = os.path.normpath(path)

    output = parsed_arg.output
    if output == '-':
        dry_run = True
        print(f'output:    (dry-run)')
    else:
        if not os.path.isabs(output):
            output = os.path.abspath(output)
        output = os.path.normpath(output)
        print(f'output:  {output}')
        dry_run = False

    filetypes = list(parsed_arg.filetype) if parsed_arg.filetype else None
    if filetypes == None:
        print(f'filetypes: any')
    else:
        print(f'filetypes: {filetypes}')

    fileexts = list(parsed_arg.fileext) if parsed_arg.fileext else None
    if fileexts == None:
        print(f'fileexts: any')
    else:
        fileexts = [v for x in fileexts for v in x.split(',')]
        print(f'fileexts: {fileexts}')

    logfile = parsed_arg.logfile
    if logfile:
        if not os.path.isabs(logfile):
            logfile = os.path.abspath(logfile)
    else:
        logfile = None
    print(f'logfile: {logfile}')

    filelist = parsed_arg.filelist
    if filelist:
        if not os.path.isabs(filelist):
            filelist = os.path.abspath(filelist)
    else:
        filelist = None
    print(f'filelist: {filelist}')

    tempdir = parsed_arg.tempdir

    print('----\n')
    do_extract(
        input_path=path,
        output_dir=output,
        filetypes=filetypes,
        fileexts=fileexts,
        logfile=logfile,
        filelist_path=filelist,
        calc_md5=parsed_arg.calc_md5,
        calc_sha1=parsed_arg.calc_sha1,
        dry_run=dry_run
    )


def demo():
    input_path = 'data/test_cases/1.docx'
    output_dir = 'data/test_cases/ext'
    filelist_path = 'data/test_cases/file_list.json'

    filelist= do_extract(
        input_path=input_path,
        output_dir=output_dir,
        filelist_path=filelist_path,
    )
    print(filelist)

if __name__ == '__main__':
    # main()
    demo()