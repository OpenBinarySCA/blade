FROM tiangolo/uvicorn-gunicorn:python3.11

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    unar liblzo2-dev zstd git build-essential pkg-config libzip-dev curl \
    squashfs-tools liblzma-dev liblzo2-dev zlib1g-dev unyaffs \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# 手动安装 binwalk2
RUN pip install --no-cache-dir --upgrade pip setuptools wheel
RUN pip install --no-cache-dir "git+https://github.com/ReFirmLabs/binwalk@v2.3.4"

### 以下是binwalk3的安装方法，因其策略严格且sasquatch安装不稳定，暂时不使用
## 安装 sasquatch
#RUN git clone https://github.com/devttys0/sasquatch /opt/sasquatch \
#    && cd /opt/sasquatch \
#    && ./build.sh \
#    && cp sasquatch /usr/local/bin/ \
#    && cd / && rm -rf /opt/sasquatch

## 安装 Rust 和 Cargo
#RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
#ENV PATH="/root/.cargo/bin:${PATH}"
#
## 使用 Cargo 安装 binwalk
#RUN cargo install binwalk

# 安装编译依赖和 radare2
RUN git clone https://github.com/radareorg/radare2 /opt/radare2 \
    && cd /opt/radare2 && sys/install.sh
# 把 radare2 的 bin 路径加入环境变量
ENV PATH="/usr/local/bin:${PATH}"

# 复制requirements.txt 并安装python依赖
COPY requirements.txt /tmp/
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# 复制app代码，docker部署api测试时不开启
COPY app /app/app

# 复制启动脚本，并赋予执行权限
COPY compose/start.sh /app/start.sh
RUN chmod +x /app/start.sh

CMD ["/app/start.sh"]
