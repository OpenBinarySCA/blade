"""
Binary String Extraction Utilities
提取二进制文件中的字符串
"""
from typing import List
from loguru import logger


def extract_binary_strings(binary_path, tool='radare2'):
    """
    提取二进制文件中的字符串
    :param binary_path: 二进制文件路径
    :param tool: 使用的工具，可选 'strings' 或 'radare2'
    :return: 提取的字符串列表（去重后）
    """
    try:
        import subprocess
        import os
        import json

        # 检查文件是否存在
        if not os.path.exists(binary_path):
            raise FileNotFoundError(f"文件不存在: {binary_path}")

        if tool.lower() == 'strings':
            # 调用 strings 命令提取字符串
            result = subprocess.run(['strings', binary_path], capture_output=True, text=True)

            if result.returncode != 0:
                raise Exception(f"strings 命令执行失败: {result.stderr}")

            # 分割输出并去重
            strings_list = result.stdout.splitlines()

        elif tool.lower() == 'radare2' or tool.lower() == 'r2':
            try:
                # 导入r2pipe库
                import r2pipe

                # 打开二进制文件
                r2 = r2pipe.open(binary_path, flags=[
                    "-e bin.relocs.apply=true",
                    "-e bin.cache=true"])

                # 获取所有字符串
                all_strings = r2.cmdj("izzj")

                # 使用集合去重（因为同一字符串可能在多个段出现）
                strings_set = set()
                strings_list = []

                # 过滤只保留.data和.rodata段的字符串
                if all_strings:
                    for string_obj in all_strings:
                        if 'string' in string_obj and 'vaddr' in string_obj:
                            string = string_obj['string']

                            # 跳过空字符串或过短的字符串（可选）
                            # if not string or len(string) < 2:
                            #     continue

                            # 提取完整字符串（保留尾随空格）
                            raw_string = r2.cmd(f"prz 100 @ {string_obj['vaddr']}")
                            if raw_string:
                                trailing_spaces = 0
                                for i in range(len(raw_string) - 1, -1, -1):
                                    if raw_string[i] == ' ':
                                        trailing_spaces += 1
                                    else:
                                        break

                                if trailing_spaces > 0:
                                    string += ' ' * trailing_spaces

                            # 去重：只添加未见过的字符串
                            if string not in strings_set:
                                strings_set.add(string)
                                strings_list.append(string)

                # 关闭r2连接
                r2.quit()

            except ImportError:
                raise Exception("找不到r2pipe库，请先安装：pip install r2pipe")
            except Exception as e:
                raise Exception(f"使用r2pipe提取字符串时出错: {str(e)}")
        else:
            raise ValueError(f"不支持的工具: {tool}，请使用 'strings' 或 'radare2'")

        # 去重
        unique_strings = list(set(strings_list))

        # 长度筛选
        unique_strings = [s for s in unique_strings if 4 < len(s) < 1000]
        return unique_strings

    except FileNotFoundError as e:
        logger.error(f"File not found: {e}")
        return []
    except Exception as e:
        logger.error(f"Error extracting strings: {e}")
        return []
