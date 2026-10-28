import os.path
from queue import Queue
from typing import List

import tree_sitter_c as tsc
import tree_sitter_cpp as tscpp
from loguru import logger
from tree_sitter import Language, Parser, Node

from ..constants import C_EXTENSION_SET, CPP_EXTENSION_SET
from ..interface import FileFeature, NodeType, FunctionFeature
from ..tools import calculate_sha256

C_LANGUAGE = Language(tsc.language())
CPP_LANGUAGE = Language(tscpp.language())

import threading
import functools

import os

import re


def extract_functions(file_path):
    potential_lines = []
    macro_names = set()

    # 1. 收集所有潜在的函数定义/声明行，并识别宏定义
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        in_multiline_comment = False
        in_macro_definition = False
        current_macro = None

        for line in f:
            # 处理多行宏定义
            if in_macro_definition:
                if not line.strip().endswith('\\'):
                    in_macro_definition = False
                continue

            # 检查新的宏定义
            macro_match = re.match(r'^\s*#\s*define\s+([a-zA-Z_]\w*)\s*\(', line)
            if macro_match:
                macro_names.add(macro_match.group(1))
                if line.strip().endswith('\\'):
                    in_macro_definition = True
                    current_macro = macro_match.group(1)
                continue

            # 处理多行注释
            if '/*' in line and not in_multiline_comment:
                in_multiline_comment = True
                if '*/' in line[line.find('/*') + 2:]:
                    in_multiline_comment = False
                    line = re.sub(r'/\*.*?\*/', ' ', line)
                else:
                    line = line[:line.find('/*')]
            elif '*/' in line and in_multiline_comment:
                in_multiline_comment = False
                line = line[line.find('*/') + 2:]
            elif in_multiline_comment:
                continue

            # 处理单行注释
            if '//' in line:
                line = line[:line.find('//')]

            # 快速检查: 有标识符后跟括号?
            if re.search(r'\b[a-zA-Z_]\w*\s*\(', line):
                potential_lines.append(line)

    # 2. 从筛选出的行中提取函数名
    # 扩展的C/C++关键字和控制结构列表
    excluded = {'if', 'while', 'for', 'switch', 'return', 'sizeof', 'typeof',
                'else', 'do', 'case', 'default', 'typedef', 'struct', 'union',
                'enum', 'goto', 'break', 'continue', 'static', 'extern', 'const',
                'inline', 'volatile', 'register', 'restrict', 'class', 'template',
                'namespace', 'throw', 'try', 'catch', 'new', 'delete', 'operator',
                'friend', 'virtual', 'explicit', 'using', 'true', 'false', 'nullptr',
                'void', 'int', 'char', 'float', 'double', 'bool', 'short', 'long',
                'unsigned', 'signed', 'auto', 'decltype', 'constexpr'}

    functions = set()
    for line in potential_lines:
        # 找出所有形如标识符+括号的模式
        for match in re.finditer(r'\b([a-zA-Z_]\w*)\s*\(', line):
            func = match.group(1)
            if func not in excluded and func not in macro_names:
                functions.add(func)

    # 3. 后处理: 排除明显是函数调用的标识符
    not_functions = set()

    # 定义所有需要排除的函数调用模式
    call_patterns = [
        # 原有模式
        r'=\s*([a-zA-Z_]\w*)\s*\(',           # 赋值右侧: x = func(
        r',\s*([a-zA-Z_]\w*)\s*\(',           # 函数参数: foo(a, func(
        r'(?:if|while)\s*\(\s*([a-zA-Z_]\w*)\s*\(',  # 条件语句: if (func(

        # 成员函数调用（最关键的补充）
        r'->\s*([a-zA-Z_]\w*)\s*\(',          # 指针调用: obj->func(
        r'\.\s*([a-zA-Z_]\w*)\s*\(',          # 对象调用: obj.func(
        r'::\s*([a-zA-Z_]\w*)\s*\(',          # 作用域调用: Class::func( (静态方法调用)

        # 控制流和返回语句
        r'\breturn\s+([a-zA-Z_]\w*)\s*\(',    # 返回语句: return func(
        r'\bthrow\s+([a-zA-Z_]\w*)\s*\(',     # 抛出异常: throw func(
        r'\bcase\s+([a-zA-Z_]\w*)\s*\(',      # case 语句: case func(

        # 逻辑和比较运算符后
        r'!\s*([a-zA-Z_]\w*)\s*\(',           # 逻辑非: !func(
        r'&&\s*([a-zA-Z_]\w*)\s*\(',          # 逻辑与: && func(
        r'\|\|\s*([a-zA-Z_]\w*)\s*\(',        # 逻辑或: || func(
        r'==\s*([a-zA-Z_]\w*)\s*\(',          # 等于: == func(
        r'!=\s*([a-zA-Z_]\w*)\s*\(',          # 不等于: != func(
        r'<=?\s*([a-zA-Z_]\w*)\s*\(',         # 小于等于: < func( 或 <= func(
        r'>=?\s*([a-zA-Z_]\w*)\s*\(',         # 大于等于: > func( 或 >= func(

        # 算术运算符后
        r'\+\s*([a-zA-Z_]\w*)\s*\(',          # 加法: + func(
        r'-\s*([a-zA-Z_]\w*)\s*\(',           # 减法: - func(
        r'\*\s*([a-zA-Z_]\w*)\s*\(',          # 乘法: * func(
        r'/\s*([a-zA-Z_]\w*)\s*\(',           # 除法: / func(
        r'%\s*([a-zA-Z_]\w*)\s*\(',           # 取模: % func(

        # 括号和其他分隔符后
        r'\(\s*([a-zA-Z_]\w*)\s*\(\s*[^)]*\)\s*\)',  # 类型转换或嵌套: (func(...))
        r'\[\s*([a-zA-Z_]\w*)\s*\(',          # 数组下标: [func(
        r'\{\s*([a-zA-Z_]\w*)\s*\(',          # 初始化列表: {func(
        r'\?\s*([a-zA-Z_]\w*)\s*\(',          # 三元运算符: ? func(
        r':\s*([a-zA-Z_]\w*)\s*\([^;]*[,)]',  # 初始化列表或三元: : func(...), 或 : func(...))

        # 位运算符后
        r'&\s*([a-zA-Z_]\w*)\s*\(',           # 位与或取地址后: & func(
        r'\|\s*([a-zA-Z_]\w*)\s*\(',          # 位或: | func(
        r'\^\s*([a-zA-Z_]\w*)\s*\(',          # 位异或: ^ func(
        r'<<\s*([a-zA-Z_]\w*)\s*\(',          # 左移: << func(
        r'>>\s*([a-zA-Z_]\w*)\s*\(',          # 右移: >> func(
    ]

    for line in potential_lines:
        for pattern in call_patterns:
            for match in re.finditer(pattern, line):
                not_functions.add(match.group(1))

    # 返回结果
    result = sorted(list(functions - not_functions))
    return result


def extract_strings(file_path):
    """
    从文件中提取所有双引号之间的字符串，排除注释和包含语句中的字符串

    Args:
        file_path: 文件路径

    Returns:
        list: 提取到的字符串列表
    """
    import re

    strings = []

    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()

        # 移除C风格注释 /* ... */
        content = re.sub(r'/\*[\s\S]*?\*/', '', content)

        # 移除C++风格注释 // ...
        content = re.sub(r'//.*?$', '', content, flags=re.MULTILINE)

        # 移除包含语句 #include "..."
        content = re.sub(r'#include\s*"[^"]*"', '', content)
        content = re.sub(r'#include\s*<[^>]*>', '', content)

        # 提取所有双引号之间的字符串
        string_matches = re.finditer(r'"((?:\\.|[^"\\])*)"', content)
        for match in string_matches:
            strings.append(match.group(1))

    return strings


def timeout(seconds):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            class TimeoutError(Exception):
                pass

            def target():
                wrapper.result = func(*args, **kwargs)

            thread = threading.Thread(target=target)
            thread.daemon = True
            thread.start()
            thread.join(seconds)

            if thread.is_alive():
                raise TimeoutError(f"Function {func.__name__} timed out after {seconds} seconds")
            return wrapper.result

        return wrapper

    return decorator

class FileFeatureExtractor:

    def __init__(self, file_path, file_size_limit_mb=10, extract_source_code=False):
        """

        :param file_path: 要提取的文件绝对路径
        :param file_size_limit_mb: 文件大小限制（MB），超过限制不提取
        :param extract_source_code: 是否提取源代码

        """
        self.file_path = file_path
        self.file_size_limit_mb = file_size_limit_mb
        self.extract_source_code = extract_source_code

        self.root_node: Node = None
        self.src_lines: List[str] = []

        self.function_dict = dict()

    def read_callable_point(self, byte_offset, point):
        row, column = point
        if row >= len(self.src_lines) or column >= len(self.src_lines[row]):
            return None
        return self.src_lines[row][column:].encode('utf8')

    def init_src_lines_and_root_node(self):
        if self.file_path.endswith(tuple(C_EXTENSION_SET)):
            parser = Parser(C_LANGUAGE)
        elif self.file_path.endswith(tuple(CPP_EXTENSION_SET)):
            parser = Parser(CPP_LANGUAGE)
        else:
            raise Exception(f"Unrecognized File Extension in Path: {self.file_path}")

        with open(self.file_path, 'r', encoding='utf-8', errors='ignore') as f:
            self.src_lines = f.readlines()

        tree = parser.parse(self.read_callable_point)

        self.root_node = tree.root_node

    def extract(self) -> FileFeature:
        # 提取基本特征
        file_name = os.path.basename(self.file_path)
        pure_name, extension = os.path.splitext(file_name)
        file_size_kb = round(os.path.getsize(self.file_path) / 1024, 2)
        global_strings = []
        may_missed_function_names = []

        try:
            # tree-sitter 解析，超过限制（10M），不提取
            if file_size_kb / 1024 <= self.file_size_limit_mb:
                # 提取函数特征
                extraction_succeed, extraction_log = self.extract_function_features()

                # 提取文件全部字符串
                # file_strings = set(extract_strings(self.file_path))
                file_strings = set(self.find_string_literals(self.root_node))

                # 提取全部函数名
                extracted_function_names = set(self.function_dict.keys())
                all_function_names = extract_functions(self.file_path)

                may_missed_function_names = set(all_function_names) - extracted_function_names

                # 计算出不在函数中的字符串，即全局字符串
                function_strings = set()
                for src_function in self.function_dict.values():
                    function_strings.update(src_function.string_literals)
                global_strings = list(file_strings - function_strings)

            else:
                extraction_succeed = False
                extraction_log = f"file size = {file_size_kb / 1024} > file_size_limit_mb = {self.file_size_limit_mb}"

        except Exception as e:
            err_msg = f"extract {self.file_path} failed, error: {e}"
            logger.error(err_msg)
            extraction_succeed = False
            extraction_log = err_msg

        all_strings = set()
        for src_function in self.function_dict.values():
            all_strings.update(src_function.string_literals)
        all_strings.update(global_strings)

        # 生成文件对象
        file_feature = FileFeature(
            name=file_name,
            extension=extension,
            path=self.file_path,
            file_size_kb=file_size_kb,
            sha256=calculate_sha256(self.file_path),
            function_num=len(self.function_dict),
            distinct_string_num=len(all_strings),
            functions=list(self.function_dict.values()),
            global_strings=global_strings,
            may_missed_function_names=list(may_missed_function_names),
        )

        # 如果失败了，记录失败原因
        if not extraction_succeed:
            file_feature.extraction_succeed = False
            file_feature.extraction_log = extraction_log

        return file_feature

    # @timeout(10)
    def extract_function_features(self):
        extraction_succeed = True
        extraction_log = None

        try:
            self.init_src_lines_and_root_node()
            self.extract_functions()
        # 文件编码错误
        except UnicodeDecodeError as e:
            extraction_succeed = False
            extraction_log = str(e)
        # 执行超时
        except TimeoutError:
            extraction_succeed = False
            extraction_log = f"extraction timed out 10 seconds."
        # 其他错误
        except Exception as e:
            raise e

        return extraction_succeed, extraction_log

    def extract_functions(self):
        stack = [(self.root_node, 0)]
        function_node_values = NodeType.get_function_node_values()
        while stack:
            current_node, level = stack.pop()

            if current_node.type in function_node_values:
                self.parse_function_node(current_node)

            # 将子节点按逆序压入栈中
            stack.extend((child_node, level + 1) for child_node in reversed(current_node.children))

    def parse_node_content(self, node):
        """

        :param start_point: 起始点
        :param end_point: 结束点
        :return: List[str]
        """
        start_row, start_column = node.start_point
        end_row, end_column = node.end_point

        content_lines = []
        if start_row >= len(self.src_lines):
            return content_lines

        elif start_row == end_row:
            content_lines.append(self.src_lines[start_row][start_column:end_column])
        else:
            # 起始行
            content_lines.append(self.src_lines[start_row][start_column:])
            # 中间行
            content_lines.extend(self.src_lines[start_row + 1:end_row])
            # 结束行
            content_lines.append(self.src_lines[end_row][:end_column + 1])
        return content_lines

    def process_node_name(self, node_name):
        # 处理带有指针返回类型的函数
        # 例如: "X509_LOOKUP_METHOD *X509_LOOKUP_hash_dir(void)"
        match = re.search(r'(\w+(?:\s*\*)?)\s+(\w+)\s*\(', node_name)
        if match:
            return match.group(2)  # 返回实际的函数名

        # 原有的处理逻辑
        if "(" in node_name:
            node_name = node_name.split('(')[0]

        node_name = node_name.replace("* ", "")
        node_name = node_name.strip()
        return node_name

    def extract_string_content(self, node):
        content = ""
        for children_node in node.children:
            if children_node.type != '"':
                # 提取字符串内容（去掉引号）
                content += self.parse_node_content(children_node)[0]
        return content

    def find_string_literals(self, node, print_node=False):
        string_literals = []
        queue = Queue()
        queue.put(node)

        # 用于临时存储连续字符串
        consecutive_strings = []

        while not queue.empty():
            current_node = queue.get()
            # content = self.parse_node_content(current_node)[0]
            # print(current_node.type, content)

            # 这些节点直接跳过
            if current_node.type in {"comment", "preproc_include"}:
                continue

            if current_node.type == "preproc_arg":
                content = self.parse_node_content(current_node)[0]
                # print(content)
                if content.startswith('"') and content.endswith('"'):
                    content = content[1:-1]
                    # 如果有待处理的连续字符串，先处理它们
                    if consecutive_strings:
                        string_literals.append("".join(consecutive_strings))
                        consecutive_strings = []
                    string_literals.append(content)
                    continue

            # 字符串节点
            if current_node.type == 'string_literal':
                content = self.extract_string_content(current_node)
                # print(content)
                # 将当前字符串添加到连续字符串列表
                consecutive_strings.append(content)
                # 无需继续遍历子节点
                continue
            else:
                # 如果当前节点不是字符串，且有待处理的连续字符串
                if consecutive_strings:
                    # 合并所有连续字符串并添加到结果列表
                    string_literals.append("".join(consecutive_strings))
                    # 清空连续字符串列表
                    consecutive_strings = []

            # 将所有子节点添加到队列
            for child in current_node.children:
                queue.put(child)

        # 处理队列结束后可能还有未处理的连续字符串
        if consecutive_strings:
            string_literals.append("".join(consecutive_strings))

        return string_literals


    def parse_function_node(self, node):
        body_node = node.child_by_field_name('body')
        if not body_node:
            return

        # 解析函数类型，名称
        identifier_node = node.child_by_field_name('declarator')
        node_type = identifier_node.type
        # 获取声明器的所有内容行
        declaration_lines = self.parse_node_content(identifier_node)
        # 合并为一个字符串
        node_name = ' '.join([line.strip() for line in declaration_lines])
        if node_type == "function_declarator" and node_name.startswith("if ("):
            return
        elif '\t' in node_name:
            return

        # 函数基本信息
        function_name = self.process_node_name(node_name)
        start_line = node.start_point[0] + 1
        end_line = node.end_point[0] + 1
        source_codes = self.src_lines[start_line - 1:end_line]

        # 字符串

        string_literals = list(set(self.find_string_literals(node)))

        # 函数调用
        function_calls = self.find_function_calls(body_node)

        src_function = FunctionFeature(
            name=function_name,
            start_line=start_line,
            end_line=end_line,
            source_codes=source_codes if self.extract_source_code else None,
            file_path=self.file_path,
            distinct_string_num=len(string_literals),
            function_calls=function_calls,
            string_literals=string_literals
        )
        self.function_dict[function_name] = src_function

    def find_function_calls(self, node):
        """
        查找函数节点内的所有函数调用

        Args:
            node: 函数体节点

        Returns:
            list: 被调用函数的名称列表
        """
        function_calls = []
        queue = Queue()
        queue.put(node)

        while not queue.empty():
            current_node = queue.get()

            # 跳过注释和预处理指令
            if current_node.type in {"comment", "preproc_include", "preproc_if", "preproc_ifdef", "preproc_else"}:
                continue

            # 检查是否是函数调用
            if current_node.type == "call_expression":
                # 获取函数名节点
                function_node = current_node.child_by_field_name('function')
                if function_node:
                    # 直接函数调用 (func())
                    if function_node.type == "identifier":
                        function_name = self.parse_node_content(function_node)[0].strip()
                        function_calls.append(function_name)
                    # 成员函数调用 (obj.method())
                    elif function_node.type == "field_expression":
                        method_node = function_node.child_by_field_name('field')
                        if method_node and method_node.type == "field_identifier":
                            method_name = self.parse_node_content(method_node)[0].strip()
                            function_calls.append(method_name)

            # 将所有子节点添加到队列
            for child in current_node.children:
                queue.put(child)

        # 返回唯一的函数调用列表
        return list(set(function_calls))

def extract_src_file_feature(path) -> FileFeature:
    file_extractor = FileFeatureExtractor(file_path=path, extract_source_code=False)
    file_feature = file_extractor.extract()
    return file_feature
