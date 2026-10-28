import json
import re
import sys
from datetime import datetime

from environs import Env
from loguru import logger

from data_management.benchmark_management.conan_benchmark_generation.interface import Binary, Library, CompileConfig, LibraryReuse, \
    Benchmark, TestSoftware, TestBinarySuite, TestBinarySuiteStat

env = Env()
env.read_env()
logger.remove()
logger.add(sys.stderr, level="INFO")


def load_json(file_path: str) -> dict:
    """
    Load the library information from a JSON file.

    Args:
        lib_info_path (str): Path to the JSON file containing library information.

    Returns:
        dict: Parsed JSON data.
    """
    import json

    with open(file_path, 'r') as file:
        lib_info = json.load(file)

    return lib_info


from typing import List, Dict

import os
import subprocess


def is_elf_binary(file_path: str) -> bool:
    """
    使用file命令检查文件是否是ELF二进制文件
    """
    try:
        # 检查文件是否存在
        if not os.path.exists(file_path):
            print(f"文件不存在: {file_path}")
            return False

        # 1. 文件名检查 - 明确的非二进制文件扩展名
        file_name = os.path.basename(file_path)
        non_binary_extensions = {
            '.a', '.txt', '.md', '.sh', '.py', '.json', '.xml', '.yaml', '.yml',
            '.conf', '.cfg', '.ini', '.log', '.html', '.css', '.js', '.sql',
            '.csv', '.tsv', '.properties', '.gitignore', '.dockerfile',
            '.makefile', '.cmake', '.pc', '.la', '.prl', '.pri'
        }

        # 检查文件扩展名
        file_lower = file_name.lower()
        for ext in non_binary_extensions:
            if file_lower.endswith(ext):
                return False

        # 特殊情况：一些没有扩展名但明确是文本的文件
        text_file_names = {
            'readme', 'license', 'copyright', 'changelog', 'authors',
            'contributors', 'makefile', 'dockerfile', 'cmakelists.txt'
        }
        if file_lower in text_file_names:
            return False

        # 2. 使用file命令检查文件类型
        result = subprocess.run(['file', file_path],
                                capture_output=True,
                                text=True,
                                timeout=10)  # 增加超时时间
        if result.returncode != 0:
            print(f"file命令执行失败: {file_path}")
            return False

        file_output = result.stdout.strip()
        # 移除文件路径，只保留文件类型描述
        if ':' in file_output:
            file_output = file_output.split(':', 1)[1].strip()
        file_output_lower = file_output.lower()

        # 2.1 明确的脚本和文本文件类型
        script_indicators = [
            'shell script',
            'perl script',
            'python script',
            'text executable',
            'ascii text',
            'utf-8 text',
            'unicode text',
            'xml document',
            'json data',
            'html document',
            'makefile script',
            'c source',
            'c++ source',
            'symbolic link'
        ]

        for script_type in script_indicators:
            if script_type in file_output_lower:
                return False

        # 2.2 明确的二进制文件类型
        # 共享库文件 (.so) - 但要确保确实是ELF格式
        if '.so' in file_name and 'elf' in file_output_lower:
            return True

        # 2.3 ELF文件检查
        if 'elf' in file_output_lower:
            # 进一步检查ELF文件类型
            elf_types = [
                'executable',  # 可执行文件
                'shared object',  # 共享库
            ]

            for elf_type in elf_types:
                if elf_type in file_output_lower:
                    return True

            # 如果包含ELF但没有具体类型，返回False
            return False

        # 3. 未知文件类型 - 打印日志
        print(f"未知文件类型: {file_name}")
        print(f"路径: {file_path}")
        print(f"file输出: {file_output}")
        return False

    except subprocess.TimeoutExpired:
        print(f"file命令超时: {file_path}")
        return False
    except Exception as e:
        print(f"检查文件时出错 {file_path}: {e}")
        return False




def generate_benchmark(conan_libs_builder_output_dir, src_lib_info: dict, min_reused_lib_num: int = 1) -> List[
    TestSoftware]:
    test_software_dict = {}
    failed_find_binary_cases = set()
    for src_lib_name, src_lib_data in src_lib_info.items():
        for src_lib_ver, src_lib_ver_data in src_lib_data.items():
            for compile_config, compile_data in src_lib_ver_data.items():
                metadata_json_path = compile_data.get("metadata_json")
                if not os.path.exists(metadata_json_path):
                    continue
                metadata = load_json(metadata_json_path) if metadata_json_path else {}

                binary_info = compile_data.get("binary_info")
                real_reused_tpl_names = list(binary_info.keys())

                # 1. 源库信息
                test_software = get_test_software(metadata, src_lib_name, src_lib_ver, test_software_dict)


                # 2. reused_libraries
                library_reuses = get_library_reuses(metadata, real_reused_tpl_names, src_lib_name)
                rel_reused_lib_num = len([reuse for reuse in library_reuses if reuse.is_real_used])

                # 过滤条件1： test_suite 至少 n 个第三方库
                if rel_reused_lib_num < min_reused_lib_num:
                    continue  # Skip this test case if reused libraries are less than the minimum required


                # 3. 编译配置
                compile_config = CompileConfig(
                    conan_version=metadata.get("build_info", {}).get("conan_version", ""),
                    profile=os.path.basename(metadata.get("build_configuration", {}).get("profile", "")),
                )
                # 过滤条件2： 跳过静态链接编译的
                if "-static" in compile_config.profile:
                    continue

                # 4. 编译好的二进制文件
                binary_dict = get_target_binaries(binary_info, conan_libs_builder_output_dir, failed_find_binary_cases)

                # 过滤条件3：没有二进制测试用例的跳过。
                if not binary_dict:
                    continue

                # 5. 生成测试套件
                # 根据找到的测试用例的情况，更新reuse的测试用例覆盖情况
                for lib_reuse in library_reuses:
                    if lib_reuse.library.name in binary_dict:
                        lib_reuse.has_tc = True

                test_suite = TestBinarySuite(
                    stat=TestBinarySuiteStat(
                        total_reused_library=rel_reused_lib_num,
                        total_binaries=sum(len(binaries) for binaries in binary_dict.values()),
                        bin_binaries= sum(len([b for b in binaries if b.type == 'bin']) for binaries in binary_dict.values()),
                        lib_binaries= sum(len([b for b in binaries if b.type == 'lib']) for binaries in binary_dict.values()),
                    ),
                    library_reuses=library_reuses,
                    compile_config=compile_config,
                    binaries=binary_dict
                )


                # 6. 添加到测试软件
                test_software.test_binary_suites.append(test_suite)

    for case in sorted(failed_find_binary_cases):
        print(case)

    # 过滤掉空的
    test_softwares = [ts for ts in test_software_dict.values() if ts.test_binary_suites]
    return test_softwares

def find_target_bin(library_name: str,
                    binary_files: List[str],
                    whitelist: Dict[str, str] = None) -> List[str]:
    """
    找到匹配的主要二进制文件

    Args:
        library_name: 库名（如 "grpc", "protobuf", "openssl"）
        binary_files: 所有二进制文件名的列表（包括bin和lib目录下的）
        whitelist: 白名单字典，键为库名，值为对应的二进制文件名

    Returns:
        匹配的二进制文件名列表，如果没找到返回空列表
    """
    matches = []
    whitelist = {
        # A
        'aaf': ['libcom-api.so'],  # Advanced Authoring Format主要的COM API库，其他组件依赖它
        'abseil': ['libabsl_base.so'],  # Abseil基础库，所有其他Abseil代码都依赖它（更新为最新版本）
        'accellera-uvm-systemc': ['libuvm-systemc-1.0-beta4.so'],  # Accellera UVM SystemC库
        'amqp-cpp': ['libamqpcpp.so'],  # AMQP C++客户端库
        'andreasbuhr-cppcoro': ['libcppcoro.so'],  # C++协程库
        'antlr4-cppruntime': ['libantlr4-runtime.so'],  # ANTLR4 C++运行时
        'apr': ['libapr-1.so'],  # Apache可移植运行时
        'apr-util': ['libaprutil-1.so'],  # Apache可移植运行时工具库
        'asyncplusplus': ['libasync++.so'],  # Async++异步编程库
        'atk': ['libatk-1.0.so'],  # ATK可访问工具包
        'avahi': ['libavahi-core.so'],  # Avahi核心服务发现库
        'aws-kvs-pic': ['libkvspic.so'],  # AWS Kinesis Video Streams主库
        'aws-lambda-cpp': ['libaws-lambda-runtime.so'],  # AWS Lambda运行时
        'aws-libfabric': ['libfabric.so'],  # libfabric主库
        'azure-sdk-for-cpp': ['libazure-core.so'],  # Azure核心库，其他组件依赖它
        'azure-storage-cpp': ['libazurestorage.so'],  # Azure存储C++库

        # B
        'backward-cpp': ['libbackward.so'],  # 堆栈跟踪库
        'baical-p7': ['libp7-shared.so'],  # P7日志库
        'bdwgc': ['libgc.so'],  # Boehm垃圾收集器
        'behaviortree.cpp': ['libbehaviortree_cpp.so'],  # 行为树C++库
        'binutils': ['aarch64-pc-linux-gnu-ld.bfd', 'x86_64-pc-linux-gnu-ld.bfd'],  # GNU链接器（支持多架构）
        'boost': ['libboost_system.so'],  # Boost系统库（最基础和常用的，更新为最新版本）
        'breakpad': ['minidump_stackwalk'],  # 崩溃报告分析工具（最常用的）
        'brotli': ['libbrotlicommon.so'],  # Brotli通用组件（其他依赖此组件）
        'bullet3': ['libBulletDynamics.so'],  # Bullet物理引擎动力学库（核心）

        # C
        'c-ares': ['libcares.so'],  # C-Ares异步DNS解析库（更新版本）
        'c-blosc': ['libblosc.so'],  # Blosc压缩库
        'c-blosc2': ['libblosc2.so'],  # Blosc2压缩库
        'caf': ['libcaf_core.so'],  # C++ Actor Framework核心库
        'capnproto': ['libcapnp-1.1.0.so'],  # Cap'n Proto主库
        'cassandra-cpp-driver': ['libcassandra.so'],  # Cassandra C++驱动
        'ceres-solver': ['libceres.so', 'libceres.so'],  # Ceres求解器（多版本支持）
        'cfgfile': ['cfgfile.generator'],  # 配置文件生成器
        'chipmunk2d': ['libchipmunk.so'],  # Chipmunk2D物理引擎
        'chunkio': ['libchunkio-shared.so'],  # ChunkIO库
        'cigi-ccl': ['libccl_dll.so'],  # CIGI通用类库
        'clickhouse-cpp': ['libclickhouse-cpp-lib.so'],  # ClickHouse C++客户端
        'clhep': ['libCLHEP-Vector-2.4.7.1.so'],  # CLHEP向量库（最基础的数学库）
        'clipper': ['libpolyclipping.so'],  # 多边形裁剪库
        'cnats': ['libnats.so'],  # NATS客户端库
        'cocoyaxi': ['libco.so'],  # CocoyaXi协程库
        'coin-cgl': ['libCgl.so'],  # CGL = Coin-Cgl
        'coin-clp': ['clp', 'libClp.so'],  # CLP线性规划求解器主库（包含工具和库）
        'coin-lemon': ['libemon.so'],  # LEMON图算法库
        'coin-osi': ['libOsi.so'],  # COIN OSI库
        'coin-utils': ['libCoinUtils.so', 'libCoinUtils.so'],  # COIN工具库（多版本支持）
        'compute_library': ['libarm_compute.so'],  # ARM计算库
        'coost': ['libco.so'],  # Coost协程库
        'corrade': ['libCorradeUtility.so'],  # Corrade工具库
        'cpp-ipc': ['libipc.so'],  # C++ IPC库
        'cpp-optparse': ['libOptionParser.so'],  # C++命令行选项解析库
        'cpprestsdk': ['libcpprest.so'],  # C++ REST SDK
        'cppunit': ['libcppunit-1.15.so'],  # CPPUnit测试框架
        'crashpad': ['crashpad_handler'],  # Crashpad崩溃报告
        'crossguid': ['libxg.so'],  # 跨平台GUID库
        'cyclonedds': ['libddsc.so'],  # CycloneDDS数据分发服务核心库
        'cyclonedds-cxx': ['libddscxx.so'],  # CycloneDDS C++绑定
        'cyclonedx': ['libddsc.so'],  # CycloneDDS数据分发服务核心库
        'cyrus-sasl': ['libsasl2.so'],  # SASL认证库

        # D
        'date': ['libdate-tz.so', 'libdate-tz.so'],  # 日期时间库（多版本支持）
        'dbus': ['libdbus-1.so'],  # D-Bus消息系统
        'dcmtk': ['libdcmdata.so'],  # DICOM数据处理核心库
        'dd-opentracing-cpp': ['libdd_opentracing.so'],  # Datadog OpenTracing
        'devil': ['libIL.so'],  # DevIL图像库核心
        'dfp': ['libddfp.so'],  # 十进制浮点库
        'discount': ['libmarkdown.so'],  # Discount Markdown库
        'djinni-support-lib': ['libdjinni_support_lib.so'],  # Djinni支持库
        'docopt.cpp': ['libdocopt.so'],  # docopt命令行解析库
        'drflac': ['libdr_flac.so'],  # FLAC音频解码库
        'drmp3': ['libdr_mp3.so'],  # MP3解码库
        'drwav': ['libdr_wav.so'],  # WAV音频库
        'dsp-filters': ['libDSPFilters.so'],  # DSP滤波器库

        # E
        'easyhttpcpp': ['libeasyhttp.so'],  # Easy HTTP C++库
        'editline': ['libedit.so'],  # 行编辑库
        'elfutils': ['libelf-0.190.so'],  # ELF处理主库
        'embree': ['libembree4.so'],  # Intel Embree光线追踪库
        'etc2comp': ['libEtcLib.so'],  # ETC纹理压缩库
        'etcd-cpp-apiv3': ['libetcd-cpp-api.so'],  # etcd C++ API
        'eudev': ['libudev.so'],  # eudev设备管理

        # F
        'fast-cdr': ['libfastcdr.so', 'libfastcdr.so'],  # Fast CDR序列化（多版本支持）
        'fast-dds': ['libfastrtps.so'],  # Fast DDS实时发布订阅库
        'fastnoise2': ['libFastNoise.so'],  # FastNoise2噪声生成库
        'fftw': ['libfftw3.so'],  # FFTW主库
        'fmtlog': ['libfmtlog-shared.so'],  # 格式化日志库
        'foonathan-memory': ['libfoonathan_memory-0.7.3.so'],  # 内存分配库
        'foxglove-schemas-protobuf': ['libfoxglove_schemas_protobuf.so'],  # Foxglove Protobuf
        'foxglove-websocket': ['libfoxglove_websocket.so'],  # Foxglove WebSocket库
        'freealut': ['libalut.so'],  # FreeALUT音频工具库
        'ftjam': ['jam'],  # JAM构建工具
        'ftxui': ['libftxui-component.so'],  # FTXUI组件库（核心交互组件）
        'functions-framework-cpp': ['libfunctions_framework_cpp.so'],  # Functions Framework C++

        # G
        'gcc': ['x86_64-pc-linux-gnu-gcc-12.2.0'],  # GCC编译器主程序
        'gdcm': ['libgdcmCommon.so', 'libgdcmCommon.so'],  # GDCM通用库（多版本支持）
        'gdk-pixbuf': ['libgdk_pixbuf-2.0.so'],  # GDK-PixBuf图像加载库
        'gemmlowp': ['libeight_bit_int_gemm.so'],  # GEMM低精度库
        'geotrans': ['libMSPCoordinateConversionService.so'],  # 地理坐标转换服务库
        'gf-complete': ['libgf_complete.so'],  # GF完整库
        'gflags': ['libgflags_nothreads.so'],  # Google命令行标志库
        'giflib': ['libgif.so'],  # GIF图像库
        'glib': ['libglib-2.0.so', 'libglib-2.0.so'],  # GLib主库（多版本支持）
        'glibmm': ['libglibmm-2.68.so'],  # GLib C++绑定主库
        'gobject-introspection': ['libgirepository-1.0.so'],  # GObject内省库
        'google-cloud-cpp': ['libgoogle_cloud_cpp_common.so'],  # Google Cloud C++通用库
        'googleapis': ['libgoogle_api_client_proto.so'],  # Google API客户端协议库
        'gperftools': ['libtcmalloc_minimal.so'],  # Google性能工具
        'graphene': ['libgraphene-1.0.so'],  # Graphene图形库
        'grpc-proto': ['libgrpc_health_proto.so'],  # gRPC健康检查协议
        'gsoap': ['soapcpp2'],  # gSOAP编译器
        'gstreamer': ['libgstreamer-1.0.so'],  # GStreamer主库

        # H
        'hayai': ['libhayai_main.so'],  # Hayai基准测试库
        'hdf4': ['libhdf.so'],  # HDF4主库（分层数据格式）
        'hdrhistogram-c': ['libhdr_histogram.so', 'libhdr_histogram.so'],  # HDR直方图库（多版本支持）
        'highway': ['libhwy.so', 'libhwy.so'],  # Highway SIMD库（多版本支持）
        'hyperscan': ['libhs.so'],  # Hyperscan模式匹配引擎

        # I
        'i2c-tools': ['libi2c.so'],  # I2C工具库
        'iceoryx': ['libiceoryx_posh.so'],  # Iceoryx POSH库
        'icu': ['libicuuc.so', 'libicuuc.so'],  # ICU Unicode库（多版本支持）
        'iir1': ['libiir.so'],  # IIR滤波器库
        'imath': ['libImath-3_1.so', 'libImath-3_1.so'],  # Imath数学库（多版本支持）
        'influxdb-cxx': ['libInfluxDB.so'],  # InfluxDB C++客户端
        'intel-ipsec-mb': ['libIPSec_MB.so'],  # Intel IPSec多缓冲库
        'isa-l': ['libisal.so'],  # Intel存储加速库
        'itk': ['libITKCommon-5.3.so'],  # ITK图像处理工具包通用库

        # J
        'jerryscript': ['libjerry-core.so'],  # 核心JavaScript引擎
        'jpeg-compressor': ['libjpge.so'],  # JPEG编码器
        'joltphysics': ['libJolt.so'],  # Jolt物理引擎
        'json-schema-validator': ['libnlohmann_json_schema_validator.so'],  # JSON Schema验证库
        'jxrlib': ['libjpegxr.so'],  # JPEG XR核心库

        # K
        'kealib': ['libkea.so'],  # KEA地理数据库库
        'kissfft': ['libkissfft-float.so'],  # KissFFT库
        'kuba-zip': ['libzip.so'],  # ZIP归档库

        # L
        'lcms': ['liblcms2.so'],  # Little CMS颜色管理
        'lely-core': ['liblely-co.so'],  # Lely CANopen核心库
        'level-zero': ['libze_loader.so'],  # Level Zero加载器
        'libaom-av1': ['libaom.so', 'libaom.so'],  # AOM AV1编解码器（多版本支持）
        'libalsa': ['libasound.so'],  # ALSA音频库
        'libdb': ['libdb-5.3.so'],  # Berkeley DB库
        'libelfin': ['libelf++.so'],  # ELF++库
        'libest': ['libest-3.2.0p.so'],  # EST协议库
        'libevent': ['libevent_core-2.1.so'],  # libevent核心库
        'libfdk_aac': ['libfdk-aac.so'],  # FDK AAC音频编解码库
        'libfuse': ['libfuse3.so', 'libfuse3.so'],  # FUSE文件系统库（多版本支持）
        'libgettext': ['libgnuintl.so'],  # GNU国际化库
        'libharu': ['libhpdf.so'],  # Haru PDF库
        'libjpeg-turbo': ['libjpeg.so'],  # 标准JPEG库
        'libkml': ['libkmlbase.so'],  # KML基础库（其他组件依赖）
        'liblqr': ['liblqr-1.so'],  # LQR图像缩放库
        'libmeshb': ['libMeshb.7.so'],  # 网格处理库
        'libpfm4': ['libpfm.so'],  # Performance monitoring库
        'libplist': ['libplist-2.0.so'],  # Apple属性列表库
        'libnl': ['libnl-3.so'],  # Netlink主库
        'libpng': ['libpng16.so', 'libpng16.so'],  # PNG图像库（多版本支持）
        'libpqxx': ['libpqxx-7.10.so'],  # PostgreSQL C++库
        'libressl': ['libssl.so', 'libssl.so'],  # LibreSSL主库（多版本支持）
        'libsecret': ['libsecret-1.so'],  # libsecret密钥管理
        'libsgp4': ['libsgp4s.so'],  # SGP4卫星轨道库
        'libsigcpp': ['libsigc-3.0.so', 'libsigc-3.0.so'],  # libsigc++信号库（多版本支持）
        'libsrtp': ['libsrtp2.so'],  # 安全实时传输协议库
        'libsvtav1': ['libSvtAv1Enc.so'],  # SVT-AV1编码器
        'libtool': ['libltdl.so'],  # libtool动态加载库
        'libtorrent': ['libtorrent-rasterbar.so'],  # libtorrent库
        'libultrahdr': ['libuhdr.so'],  # Ultra HDR库
        'libxcrypt': ['libcrypt.so'],  # libxcrypt加密库
        'libxls': ['libxlsreader.so'],  # XLS读取库
        'libxmlpp': ['libxml++-5.0.so'],  # libxml++ C++ XML解析库
        'lightgbm': ['lib_lightgbm.so'],  # LightGBM机器学习库
        'lightpcapng': ['liblight_pcapng.so'],  # 轻量级PCAP-NG库
        'liquid-dsp': ['libliquid.so'],  # Liquid DSP库
        'lksctp-tools': ['libsctp.so'],  # SCTP协议库
        'llama-cpp': ['libllama.so'],  # LLaMA C++推理库
        'llnl-units': ['libunits.so'],  # LLNL单位转换库
        'llvm-core': ['libLLVM.so'],  # LLVM核心库
        'llvm-openmp': ['libomp.so'],  # LLVM OpenMP
        'luajit': ['libluajit-5.1.so'],  # LuaJIT主库
        'lzham': ['liblzhamdll.so'],  # LZHAM压缩库主DLL
        'lzma_sdk': ['lzma'],  # LZMA SDK压缩工具
        'lzo': ['liblzo2.so'],  # LZO压缩库

        # M
        'mariadb-connector-c': ['libmariadb.so'],  # MariaDB C连接器
        'mariadb-connector-cpp': ['libmariadbcpp.so'],  # MariaDB C++连接器
        'mbits-lngs': ['lngs-0.7'],  # 语言工具
        'mdnsresponder': ['libdns_sd.so'],  # DNS服务发现库
        'mingw-w64': ['x86_64-w64-mingw32-gcc-10.5.0'],  # MinGW-w64 GCC编译器
        'mongo-c-driver': ['libmongoc-1.0.so'],  # MongoDB C驱动
        'mongo-cxx-driver': ['libmongocxx.so'],  # MongoDB C++驱动
        'mozjpeg': ['libjpeg.so'],  # MozJPEG库
        'mpdecimal': ['libmpdec.so'],  # 多精度十进制算术库
        'mppp': ['libmp++.so'],  # 多精度算术C++库
        'mysql-connector-cpp': ['libmysqlcppconnx.so'],  # MySQL C++连接器

        # N
        'ncurses': ['libncursesw.so'],  # NCurses宽字符库
        'net-snmp': ['libnetsnmp.so'],  # Net-SNMP库
        'nifti_clib': ['libniftiio.so'],  # NIfTI IO库
        'nmslib': ['libNonMetricSpaceLib.so'],  # 非度量空间搜索库
        'nodejs': ['node'],  # Node.js运行时
        'nspr': ['libnspr4.so'],  # Netscape可移植运行时主库
        'nsimd': ['libnsimd_cpu.so'],  # NSIMD SIMD库
        'nss': ['libnss3.so'],  # NSS网络安全服务主库
        'ntv2': ['libajantv2shared.so'],  # AJA NTV2视频库

        # O
        'odpi': ['libodpic.so'],  # Oracle数据库程序接口
        'onetbb': ['libtbb.so', 'libtbb.so.12.16'],  # Intel TBB主库（多版本支持）
        'oniguruma': ['libonig.so'],  # 正则表达式库
        'open-dis-cpp': ['libOpenDIS7.so'],  # Open DIS分布式交互仿真库（选择较新版本）
        'open-simulation-interface': ['libopen_simulation_interface.so'],  # OSI库
        'openal-soft': ['libopenal.so', 'libopenal.so.1.23.1'],
        # OpenAL音频库（多版本支持）blzhamdll.so'],  # LZHAM压缩库主DLL
        'lzo': ['liblzo2.so'],  # LZO压缩库

        # M
        'mariadb-connector-c': ['libmariadb.so'],  # MariaDB C连接器
        'mariadb-connector-cpp': ['libmariadbcpp.so'],  # MariaDB C++连接器
        'mbits-lngs': ['lngs-0.7'],  # 语言工具
        'mdnsresponder': ['libdns_sd.so'],  # DNS服务发现库
        'mingw-w64': ['x86_64-w64-mingw32-gcc-10.5.0'],  # MinGW-w64 GCC编译器
        'mongo-c-driver': ['libmongoc-1.0.so'],  # MongoDB C驱动
        'mongo-cxx-driver': ['libmongocxx.so'],  # MongoDB C++驱动
        'mozjpeg': ['libjpeg.so'],  # MozJPEG库
        'mpdecimal': ['libmpdec.so'],  # 多精度十进制算术库
        'mppp': ['libmp++.so'],  # 多精度算术C++库
        'mysql-connector-cpp': ['libmysqlcppconnx.so'],  # MySQL C++连接器

        # N
        'ncurses': ['libncursesw.so'],  # NCurses宽字符库
        'net-snmp': ['libnetsnmp.so'],  # Net-SNMP库
        'nifti_clib': ['libniftiio.so'],  # NIfTI IO库
        'nmslib': ['libNonMetricSpaceLib.so'],  # 非度量空间搜索库
        'nodejs': ['node'],  # Node.js运行时
        'nspr': ['libnspr4.so'],  # Netscape可移植运行时主库
        'nsimd': ['libnsimd_cpu.so'],  # NSIMD SIMD库
        'ntv2': ['libajantv2shared.so'],  # AJA NTV2视频库

        # O
        'odpi': ['libodpic.so'],  # Oracle数据库程序接口
        'onetbb': ['libtbb.so'],  # Intel TBB简化版
        'oniguruma': ['libonig.so'],  # 正则表达式库
        'open-dis-cpp': ['libOpenDIS7.so'],  # Open DIS分布式交互仿真库（选择较新版本）
        'open-simulation-interface': ['libopen_simulation_interface.so'],  # OSI库
        'openal-soft': ['libopenal.so'],  # OpenAL音频库
        'opencl-icd-loader': ['libOpenCL.so'],  # OpenCL加载器
        'opencore-amr': ['libopencore-amrnb.so'],  # OpenCore AMR窄带
        'openddl-parser': ['libopenddlparser.so'],  # OpenDDL解析器
        'openexr': ['libOpenEXR-3_3.so', 'libImath-2_5.so'],  # OpenEXR主库
        'openfst': ['libfst.so'],  # OpenFST主库
        'openfx': ['libOfxHost.so'],  # OpenFX插件主机库
        'opengrm': ['libthrax.so'],  # OpenGrm Thrax库
        'openjpeg': ['libopenjp2.so'],  # OpenJPEG库
        'openldap': ['libldap.so'],  # OpenLDAP库
        'openmesh': ['libOpenMeshCore.so'],  # OpenMesh核心库
        'openmpi': ['libmpi.so'],  # OpenMPI主库
        'openmvg': ['libopenMVG_system.so'],  # OpenMVG系统库（基础库）
        'openpam': ['libpam.so'],  # OpenPAM认证库
        'openssh': ['ssh'],  # SSH客户端（最核心的工具）
        'opentelemetry-cpp': ['libopentelemetry_common.so'],  # OpenTelemetry通用库
        'opentracing-cpp': ['libopentracing.so'],  # OpenTracing C++
        'openvr': ['libopenvr_api.so'],  # OpenVR虚拟现实API
        'optimlib': ['liboptim.so'],  # 优化库
        'ouster_sdk': ['libouster_client.so'],  # Ouster客户端库
        'ozz-animation': ['libozz_animation_r.so'],

        # P
        'p7zip': ['7za'],  # 7-Zip归档工具
        'pagmo2': ['libpagmo.so'],  # 优化库
        'paho-mqtt-c': ['libpaho-mqtt3as.so'],  # MQTT C客户端
        'paho-mqtt-cpp': ['libpaho-mqttpp3.so'],  # MQTT C++客户端
        'pathie-cpp': ['libpathie.so'],  # 路径处理C++库
        'pcapplusplus': ['libPcap++.so'],  # PcapPlusPlus主库
        'pcre2': ['libpcre2-8.so'],  # PCRE2 UTF-8库（最常用）
        'pdf-writer': ['libPDFWriter.so'],  # PDF写入库
        'pixman': ['libpixman-1.so'],  # Pixman像素操作库
        'platformfolders': ['libplatform_folders.so'],  # 平台文件夹库
        'poco': ['libPocoFoundation.so'],  # Poco基础库
        'poshlib': ['libposh.so'],  # POSH库
        'premake': ['premake5'],  # Premake构建配置工具
        'pro-mdnsd': ['libmdnsd.so'],  # mDNS守护进程库
        'prometheus-cpp': ['libprometheus-cpp-core.so'],  # Prometheus C++核心
        'protobuf': ['protoc-27.0.0'],  # Protocol Buffers编译器
        'protobuf-c': ['protoc-gen-c'],  # Protocol Buffers C生成器
        'pupnp': ['libupnp.so'],  # Portable UPnP库

        # Q
        'qr-code-generator': ['libqrcodegencpp.so'],  # QR码生成器C++库

        # R
        'r8brain-free-src': ['libr8brain.so'],  # R8brain音频重采样库
        'rabbitmq-c': ['librabbitmq.so'],  # RabbitMQ C客户端
        'rapidyaml': ['libryml.so'],  # RapidYAML库
        'recastnavigation': ['libDetour.so'],  # Recast Navigation主库
        'redradist-icc': ['libICC.so'],  # ICC颜色管理库
        'redis-plus-plus': ['libredis++.so'],  # Redis C++客户端
        'resiprocate': ['libresip.so'],  # reSIProcate主库
        'rg-etc1': ['librg_etc1.so'],  # ETC1纹理压缩库
        'rmlui': ['libRmlCore.so'],  # RmlUi核心库
        'rpclib': ['librpc.so'],  # RPC库
        'rttr': ['librttr_core.so'],  # RTTR运行时类型反射库
        'rvo2': ['libRVO.so'],  # RVO2碰撞避免库
        'ruy': ['libruy_frontend.so', 'libruy_context.so', 'libruy_ctx.so'],

        # S
        's2geometry': ['libs2.so'],  # S2几何库
        'sbepp': ['sbeppc'],  # SBE协议编译器
        'scnlib': ['libscn.so'],  # SCN扫描库
        'sdbus-cpp': ['libsdbus-c++.so'],  # D-Bus C++绑定
        'sentry-crashpad': ['crashpad_handler'],  # Sentry崩溃处理器
        'sentry-native': ['libsentry.so'],  # Sentry Native库
        'serd': ['libserd-0.so'],  # RDF序列化库
        'serf': ['libserf-1.so'],  # Serf HTTP客户端库
        'shapelib': ['libshp.so'],  # Shapefile处理库
        'sobjectizer': ['libso.5.8.4.so', 'libso.5.8.1.so'],  # SObjectizer actor框架
        'soci': ['libsoci_core.so'],  # SOCI数据库访问库
        'sofa': ['libsofa_c.so'],  # SOFA天文库
        'soplex': ['libsoplexshared.so'],  # SoPlex线性规划求解器
        'spirv-tools': ['libSPIRV-Tools-shared.so'],  # SPIR-V工具共享库
        'sundials': ['libsundials_cvode.so'],  # SPIR-V工具共享库
        'systemc-cci': ['libcciapi.so'],  # SystemC CCI API

        # T
        'taglib': ['libtag.so'],  # TagLib音频元数据库
        'taocpp-taopq': ['libtaopq.so'],  # TAO PostgreSQL库
        'tcl': ['libtcl8.6.so'],  # Tcl脚本语言库
        'tcp-wrappers': ['libwrap.so'],  # TCP包装器库
        'tcsbank-uri-template': ['liburi-template.so'],  # URI模板库
        'tidwall-neco': ['libneco.so'],  # Neco协程库
        'tidy-html5': ['libtidy.so'],  # HTML Tidy库
        'tinkerforge-bindings': ['libtinkerforge_bindings.so'],  # Tinkerforge绑定库
        'tiny-aes-c': ['libtiny-aes.so'],  # 轻量级AES加密库
        'tng': ['libtng_io.so'],  # TNG轨迹格式库
        'tracy': ['libTracyClient.so'],  # Tracy性能分析客户端
        'twitch-native-ipc': ['libnativeipc.so'],  # Twitch本地IPC
        'twitchtv-libsoundtrackutil': ['liblibsoundtrackutil.so'],  # Twitch音轨工具库

        # U
        'unleash-client-cpp': ['libunleash.so'],  # Unleash功能开关客户端
        'urdfdom': ['liburdfdom_model.so'],  # URDF模型库
        'userspace-rcu': ['liburcu.so'],  # 用户空间RCU主库
        'util-linux-libuuid': ['libuuid.so'],  # util-linux UUID库

        # V
        'vectorscan': ['libhs.so'],  # Vectorscan模式匹配主库
        'very-simple-smtps': ['libsmtp_lib.so'],  # 简单SMTP库
        'voropp': ['libvoro++.so'],  # Voro++ Voronoi图库

        # W
        'wasm-micro-runtime': ['libiwasm.so'],  # WebAssembly微运行时
        'wayland': ['libwayland-client.so'],  # Wayland客户端库
        'whisper-cpp': ['libwhisper.so'],  # Whisper主库
        'wslay': ['libwslay_shared.so'],  # WebSocket库

        # X
        'xapian-core': ['libxapian.so'],  # Xapian搜索引擎库
        'xerces-c': ['libxerces-c-3.2.so', 'libxerces-c-3.3.so'],  # Xerces C++ XML解析库
        'xlsxio': ['libxlsxio_read.so'],  # XLSX读取库
        'xmlsec': ['libxmlsec1.so'],  # XML安全库
        'xorg-makedepend': ['makedepend'],  # X.Org makedepend工具
        'xz_utils': ['liblzma.so'],  # XZ/LZMA压缩库

        # Z
        'zeromq': ['libzmq.so'],  # ZeroMQ消息库
        'zlib': ['libz.so'],  # zlib压缩库
        'zlib-ng': ['libz-ng.so'],  # zlib-ng压缩库
        'zmarok-semver': ['libsemver.so'],  # 语义版本库
        'zxing-cpp': ['libZXing.so'],  # ZXing条码库
        'zziplib': ['libzzip-0.so'],  # ZZip库主库
    }

    # 1. 在白名单中的是
    if whitelist and library_name in whitelist:
            target_files = whitelist[library_name]
            for file in binary_files:
                pure_file_name = file
                if '.so' in file:
                    pure_file_name = file.split('.so')[0] + '.so'
                # 如果纯文件名称在白名单中，则添加
                if pure_file_name in target_files:
                    matches.append(file)

    library_name = library_name.lower()
    # 2. 按规则匹配
    for binary_file in binary_files:

        # 提取文件名（去掉路径）
        filename = binary_file.split('/')[-1]
        filename = filename.lower()

        # 规则1: 和库的名字完全一样
        if filename == library_name:
            matches.append(binary_file)
            continue

        # 规则2: lib库名
        if filename == f"lib{library_name}":
            matches.append(binary_file)
            continue

        # 规则3: 库.so
        if filename == f"{library_name}.so":
            matches.append(binary_file)
            continue

        # 规则4: lib库.so
        if filename == f"lib{library_name}.so":
            matches.append(binary_file)
            continue

        # 规则5: 库.so.xxxx (版本号)
        pattern = f"^{re.escape(library_name)}\\.so\\."
        if re.match(pattern, filename):
            matches.append(binary_file)
            continue

        # 规则6: lib库.so.xxxx (版本号)
        pattern = f"^lib{re.escape(library_name)}\\.so\\."
        if re.match(pattern, filename):
            matches.append(binary_file)
            continue

    return list(set(matches))


def get_target_binaries(tpl_info, conan_libs_builder_output_dir, failed_cases:set):
    tpl_binaries = {}
    # 遍历所有第三方库
    for tpl_name, tpl_info in tpl_info.items():
        # 信息预处理
        tpl_info = tpl_info.get("tpl_info", {})

        tpl_name = tpl_info["tpl_name"]
        bin_bins = tpl_info.get("bin_bins", {})
        if not bin_bins:
            bin_bins = {}
        lib_bins = tpl_info.get("lib_bins", {})
        if not lib_bins:
            lib_bins = {}

        # basic info dict
        hash_to_size_dict = {}
        hash_to_path_dict = {}
        path_to_hash_dict = {}
        name_to_hash_dict = {}
        name_to_path_dict = {}
        for sha256, binary_info in {**bin_bins, **lib_bins}.items():
            binary_size = binary_info.get("size", 0)
            hash_to_size_dict[sha256] = binary_size

            binary_paths = binary_info.get("paths", [])
            hash_to_path_dict[sha256] = binary_paths[0]
            binary_paths.sort(key=lambda x: len(x), reverse=True) # 按名称长度排序

            for binary_path in binary_paths:
                # 不是二进制文件跳过。
                if not is_elf_binary(binary_path):
                    continue

                path_to_hash_dict[binary_path]  = sha256
                # name_to_hash_dict
                name = os.path.basename(binary_path)
                name_to_hash_dict[name] = sha256
                # name_to_path_dict
                name_to_path_dict[name] = binary_path
                break

        # find target binary files
        all_names = list(name_to_hash_dict.keys())

        # 直接没有二进制文件的跳过
        if not all_names:
            continue

        target_bin_names = find_target_bin(tpl_name, all_names)
        target_bin_paths = [name_to_path_dict.get(name) for name in target_bin_names if name in name_to_path_dict]

        if not target_bin_names:
            failed_cases.add(f"{tpl_name}: {all_names}")

        target_binaries = []
        for target_bin_path in target_bin_paths:
            target_bin_name = os.path.basename(target_bin_path)
            sha256 = path_to_hash_dict.get(target_bin_path, "")
            binary = Binary(
                name=target_bin_name,
                type='lib' if '.so' in target_bin_name else 'bin',
                tpl_name=tpl_name,
                rel_path=str(os.path.relpath(target_bin_path, conan_libs_builder_output_dir)),
                file_size_kb=hash_to_size_dict[sha256],
                # file_size_kb=0,
                sha256= sha256
            )
            target_binaries.append(binary)
        tpl_binaries[tpl_name] = target_binaries

    return tpl_binaries


def get_library_reuses(metadata, real_reused_tpl_names, src_lib_name):
    dependencies = metadata.get("dependencies", {}).get("dependencies", [])
    library_reuses = []
    for dep in dependencies:
        tpl_name = dep.get("name", "")
        if tpl_name == src_lib_name:
            link_type = "self"
        else:
            link_type = dep.get("link_type", "")

        reuse = LibraryReuse(
            library=Library(
                name=tpl_name,
                version=dep.get("version", "")
            ),
            is_real_used=tpl_name in real_reused_tpl_names and link_type != "header-only", # 是否是实际使用的库， 1）不是header-only 2) 有实际的库被编译
            link_type=link_type,
            level=dep.get("level", ""),
            reuse_paths=dep.get("paths", [])
        )

        library_reuses.append(reuse)
    return library_reuses


def get_test_software(metadata, src_lib_name, src_lib_ver, test_software_dict):
    if (test_software := test_software_dict.get(src_lib_name)) is None:
        source_library = metadata.get("target_library", {})
        source_library = Library(
            name=src_lib_name,
            version=src_lib_ver,
            description=source_library.get("description", ""),
            license=source_library.get("license", ""),
            homepage=source_library.get("homepage", ""),
            url=source_library.get("url", ""),
            topics=source_library.get("topics", []),
        )
        test_software_dict[src_lib_name] = test_software = TestSoftware(
            source_library=source_library,
            test_binary_suites=[]
        )
    return test_software


def main():
    # paths
    from data_management.benchmark_management.conan_benchmark_generation import paths
    conan_libs_builder_output_dir = paths.BUILDER_OUTPUT_DIR
    conan_lib_info_json = paths.LIB_INFO_JSON
    benchmark_path = paths.LIBRARY_BENCHMARK_JSON

    # Load library information
    lib_info = load_json(conan_lib_info_json)

    # Generate benchmark test cases
    test_software = generate_benchmark(conan_libs_builder_output_dir, lib_info)

    # Create benchmark
    benchmark = Benchmark(
        name="Conan Library Benchmark",  # CLB
        version=datetime.now().strftime("%Y%m%d%H%M%S"),
        test_software=test_software
    )


    # dump
    with open(benchmark_path, "w") as f:
        json.dump(benchmark.customer_serialize(), f, indent=4, ensure_ascii=False)

def benchmark_check():
    # paths
    from data_management.benchmark_management.conan_benchmark_generation import paths
    benchmark_path = paths.LIBRARY_BENCHMARK_JSON

    # Load library information
    benchmark = load_json(benchmark_path)

    benchmark = Benchmark.init_from_dict(benchmark)

    # stats
    benchmark.stat()



if __name__ == '__main__':
    main()
    benchmark_check()