# LinguaOverlay 环境要求与使用指南

本文档列出运行 LinguaOverlay 所需的软件、硬件、网络条件和完整安装步骤。

## 1. 系统要求

| 项目 | 最低要求 | 推荐配置 |
| --- | --- | --- |
| 操作系统 | Windows 10 64 位 | Windows 11 64 位 |
| 内存 | 8GB | 16GB 或以上 |
| 磁盘空间 | CPU 模式约 3GB | GPU 模式预留 8GB |
| Python | 由安装脚本创建 Python 3.11 | 不要使用 Python 3.13 |
| 网络 | 首次安装、下载模型和翻译时需要 | 稳定的宽带连接 |
| 音频 | Windows 播放设备 | Realtek 耳机或扬声器 |

## 2. 必需软件

### Git

用于下载项目：

```powershell
git --version
```

如果命令不存在，可从 [Git 官网](https://git-scm.com/download/win) 安装。

### Conda

安装脚本需要 Anaconda、Miniconda 或 Miniforge。以下任意一种均可：

- [Miniconda](https://docs.conda.io/projects/miniconda/en/latest/)
- [Anaconda](https://www.anaconda.com/download)
- [Miniforge](https://github.com/conda-forge/miniforge)

验证：

```powershell
conda --version
```

脚本会按以下顺序查找 Conda：

1. 环境变量 `CONDA_EXE`
2. 系统 `PATH` 中的 `conda.exe`
3. `D:\anaconda\Scripts\conda.exe`
4. 常见的用户级 Miniconda/Anaconda 安装路径

## 3. GPU 模式

推荐使用 NVIDIA GPU。项目已在 RTX 5060 Laptop GPU 8GB 上验证。

要求：

- 可用的 NVIDIA 显卡驱动
- 支持 CUDA 12 的显卡和驱动
- 约 6GB 以上可用显存，适合运行 `large-v3-turbo`

检查显卡：

```powershell
nvidia-smi
```

安装：

```powershell
.\install.ps1 -InstallCudaRuntime
```

安装脚本会将 CUDA 12.8 与 cuDNN 9 放入项目内的 `.runtime`，不会要求用户
全局安装 CUDA Toolkit。

诊断：

```powershell
.\run.ps1 -Diagnose
```

诊断输出应包含：

```text
CUDA compute types: ... float16 ...
```

## 4. CPU 模式

没有 NVIDIA 显卡也可以运行，但延迟会明显增加。

安装：

```powershell
.\install.ps1
```

然后编辑 `config/settings.json`：

```json
{
  "whisper_model": "small",
  "whisper_device": "cpu",
  "whisper_compute_type": "int8"
}
```

CPU 模式建议从 `small` 模型开始，不建议直接运行 `large-v3-turbo`。

## 5. Python 依赖

安装脚本会读取 `requirements.txt`，当前主要依赖如下：

| 包 | 作用 |
| --- | --- |
| `faster-whisper` | 本地日语、英语语音识别 |
| `ctranslate2` | Whisper 的高性能 CPU/GPU 推理 |
| `PyAudioWPatch` | Windows WASAPI 回环音频捕获 |
| `PySide6` | 桌面悬浮字幕和系统托盘 |
| `httpx` | MiniMax HTTP API 请求 |
| `numpy` | 音频数据和重采样处理 |
| `pytest` | 自动化测试 |

不要手动把 `.runtime` 提交到 GitHub。其他用户应在自己的电脑上运行安装脚本
生成环境。

## 6. MiniMax API

MiniMax API Key 是可选项：

- 配置 Key：显示真实中文字幕。
- 不配置 Key：可使用 `-Mock` 测试音频捕获和语音识别。

创建本地配置：

```powershell
Copy-Item .env.example .env
notepad .env
```

中国大陆账号示例：

```dotenv
MINIMAX_API_KEY=your_api_key_here
MINIMAX_BASE_URL=https://api.minimaxi.com/v1
MINIMAX_MODEL=MiniMax-M2.7-highspeed
```

海外账号示例：

```dotenv
MINIMAX_API_KEY=your_api_key_here
MINIMAX_BASE_URL=https://api.minimax.io/v1
MINIMAX_MODEL=MiniMax-M2.7-highspeed
```

不要把真实密钥写入 `.env.example`、README、源码或截图。

## 7. 完整安装流程

```powershell
git clone https://github.com/hy-8/LinguaOverlay.git
cd LinguaOverlay

# NVIDIA GPU 用户
.\install.ps1 -InstallCudaRuntime

# 创建本地密钥配置
Copy-Item .env.example .env
notepad .env

# 检查设备
.\run.ps1 -Diagnose
.\run.ps1 -ListDevices

# 先进行无 API 测试
.\run.ps1 -Mock

# 正式启动
.\run.ps1
```

也可以双击 `启动实时字幕.bat`。

## 8. 常见问题

### 找不到 Conda

确认 `conda --version` 可以运行。也可以在当前 PowerShell 会话中指定：

```powershell
$env:CONDA_EXE = "C:\Users\你的用户名\miniconda3\Scripts\conda.exe"
.\install.ps1 -InstallCudaRuntime
```

### 找不到 `cublas64_12.dll`

说明只安装了显卡驱动，但项目环境缺少 CUDA 运行库。重新运行：

```powershell
.\install.ps1 -InstallCudaRuntime
```

### 没有回环设备

运行：

```powershell
.\run.ps1 -ListDevices
```

确认 Windows 当前存在可用的耳机或扬声器，并尝试播放一段声音后重新检查。

### MiniMax 返回 401

通常是账号区域和 API 地址不一致：

- 中国大陆 Key：`https://api.minimaxi.com/v1`
- 海外 Key：`https://api.minimax.io/v1`

### 字幕延迟较高

可以尝试：

- 固定 `source_language` 为 `ja` 或 `en`
- 将模型改为 `medium` 或 `small`
- 降低 `window_seconds`
- 确认程序正在使用 CUDA，而不是 CPU

## 9. GitHub 上传检查

提交前运行：

```powershell
git status --ignored
git check-ignore .env .runtime models logs
git grep -n "sk-api-"
```

预期结果：

- `.env`、`.runtime`、`models` 和 `logs` 均被忽略。
- `git grep` 不应找到真实 API Key。
