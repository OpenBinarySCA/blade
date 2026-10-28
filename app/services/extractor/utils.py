from importlib import import_module
from pkgutil import iter_modules
import types

def walk_modules(path):
    """Loads a module and all its submodules from the given module path and
    returns them. If *any* module throws an exception while importing, that
    exception is thrown back.

    For example: walk_modules('scrapy.utils')
    """

    mods = []
    mod = import_module(path)
    mods.append(mod)
    if hasattr(mod, '__path__'):
        for _, subpath, ispkg in iter_modules(mod.__path__):
            fullpath = path + '.' + subpath
            if ispkg:
                mods += walk_modules(fullpath)
            else:
                submod = import_module(fullpath)
                mods.append(submod)
    return mods
    
def list_submodules(mod_or_path, recursive=False):
    if isinstance(mod_or_path, types.ModuleType):
        if hasattr(mod_or_path, '__path__'):
            paths = list(mod_or_path.__path__)
        else:
            return []
    elif isinstance(mod_or_path, str):
        paths = [mod_or_path]
    else:
        raise TypeError(f'mod_or_path should be <module> or <str>, got {type(mod_or_path)}')

    mods = []
    for _, name, ispkg in iter_modules(paths):
        mods.append(name)
        if recursive and ispkg:
            for child_name in list_submodules(paths[0] + '/' + name, recursive=recursive):
                mods.append(name + '.' + child_name)
    return mods


def copy_stream_to_file(stream, filepath):
    with open(filepath, 'wb+') as f:
        while True:
            buf = stream.read(1024*1024)
            if len(buf) == 0: 
                break
            f.write(buf)
