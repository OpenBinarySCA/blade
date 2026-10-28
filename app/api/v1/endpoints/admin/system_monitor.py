"""
Admin System Monitor API

系统状态监控接口
"""
import psutil
from datetime import datetime
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from .....services.auth import require_admin
from .....databases.user_data.models import User

router = APIRouter(prefix="/system", tags=["Admin - System Monitor"])


# =============================================================================
# Response Models
# =============================================================================

class CPUInfo(BaseModel):
    """CPU 信息"""
    percent: float  # CPU 使用率 (%)
    count: int  # CPU 核心数
    count_logical: int  # 逻辑 CPU 数
    freq_current: float | None  # 当前频率 (MHz)
    freq_max: float | None  # 最大频率 (MHz)


class MemoryInfo(BaseModel):
    """内存信息"""
    total: int  # 总内存 (bytes)
    available: int  # 可用内存 (bytes)
    used: int  # 已使用内存 (bytes)
    percent: float  # 使用率 (%)


class DiskInfo(BaseModel):
    """磁盘信息"""
    device: str  # 设备名
    mountpoint: str  # 挂载点
    total: int  # 总容量 (bytes)
    used: int  # 已使用 (bytes)
    free: int  # 可用 (bytes)
    percent: float  # 使用率 (%)


class DiskIOInfo(BaseModel):
    """磁盘 IO 信息"""
    read_bytes: int  # 读取字节数
    write_bytes: int  # 写入字节数
    read_count: int  # 读取次数
    write_count: int  # 写入次数


class NetworkIOInfo(BaseModel):
    """网络 IO 信息"""
    bytes_sent: int  # 发送字节数
    bytes_recv: int  # 接收字节数
    packets_sent: int  # 发送包数
    packets_recv: int  # 接收包数


class SystemStatusResponse(BaseModel):
    """系统状态响应"""
    timestamp: str
    cpu: CPUInfo
    memory: MemoryInfo
    disks: list[DiskInfo]
    disk_io: DiskIOInfo | None
    network_io: NetworkIOInfo
    boot_time: str
    uptime_seconds: int


# =============================================================================
# API Endpoints
# =============================================================================

@router.get("/status", response_model=SystemStatusResponse)
async def get_system_status(
    current_user: User = Depends(require_admin)
):
    """获取系统状态信息"""

    # CPU 信息
    cpu_freq = psutil.cpu_freq()
    cpu_info = CPUInfo(
        percent=psutil.cpu_percent(interval=0.1),
        count=psutil.cpu_count(logical=False) or 1,
        count_logical=psutil.cpu_count(logical=True) or 1,
        freq_current=cpu_freq.current if cpu_freq else None,
        freq_max=cpu_freq.max if cpu_freq else None,
    )

    # 内存信息
    mem = psutil.virtual_memory()
    memory_info = MemoryInfo(
        total=mem.total,
        available=mem.available,
        used=mem.used,
        percent=mem.percent,
    )

    # 磁盘信息
    disks = []
    for partition in psutil.disk_partitions(all=False):
        try:
            usage = psutil.disk_usage(partition.mountpoint)
            disks.append(DiskInfo(
                device=partition.device,
                mountpoint=partition.mountpoint,
                total=usage.total,
                used=usage.used,
                free=usage.free,
                percent=usage.percent,
            ))
        except (PermissionError, OSError):
            continue

    # 磁盘 IO
    disk_io = None
    try:
        io_counters = psutil.disk_io_counters()
        if io_counters:
            disk_io = DiskIOInfo(
                read_bytes=io_counters.read_bytes,
                write_bytes=io_counters.write_bytes,
                read_count=io_counters.read_count,
                write_count=io_counters.write_count,
            )
    except Exception:
        pass

    # 网络 IO
    net_io = psutil.net_io_counters()
    network_io = NetworkIOInfo(
        bytes_sent=net_io.bytes_sent,
        bytes_recv=net_io.bytes_recv,
        packets_sent=net_io.packets_sent,
        packets_recv=net_io.packets_recv,
    )

    # 启动时间和运行时长
    boot_time = datetime.fromtimestamp(psutil.boot_time())
    uptime_seconds = int((datetime.now() - boot_time).total_seconds())

    return SystemStatusResponse(
        timestamp=datetime.now().isoformat(),
        cpu=cpu_info,
        memory=memory_info,
        disks=disks,
        disk_io=disk_io,
        network_io=network_io,
        boot_time=boot_time.isoformat(),
        uptime_seconds=uptime_seconds,
    )
