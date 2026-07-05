# TES 比赛实时 AI 监听系统

> 自动识别解说语义，第一时间感知胜负。

<p align="center">
  <img src="./assets/tes_logo.png" alt="TES AI Monitor Banner" width="200">
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12-blue?logo=python" alt="Python 3.12">
  <img src="https://img.shields.io/badge/PyTorch-2.12.1-red?logo=pytorch" alt="PyTorch 2.12.1">
  <img src="https://img.shields.io/badge/CUDA-12.6-green?logo=nvidia" alt="CUDA 12.6">
  <img src="https://img.shields.io/badge/Whisper-medium-orange" alt="Whisper medium">
  <img src="https://img.shields.io/badge/DeepSeek-API-purple" alt="DeepSeek API">
</p>

---

## 项目简介

看 TES 比赛时，你是否也经历过：
- 手动盯着屏幕，生怕错过关键局势
- 传统关键词检测听不懂"寄了""被干碎了"等黑话
- 想第一时间知道结果，却被信息延迟折磨

这个项目用 **AI 语义理解** 替代机械关键词匹配，实时监听比赛解说，自动判断胜负，并在失利时播放你预设的"安慰视频"。

---

## 核心特性

| 特性 | 说明 |
|------|------|
| **实时音频采集** | 通过 pyaudiowpatch 捕获 Windows 扬声器回环音频 |
| **AI 人声检测** | Silero VAD 智能过滤 BGM、环境噪音 |
| **本地语音识别** | Whisper medium 模型，RTX 4060 CUDA 加速 |
| **语义理解** | DeepSeek API 理解自然语言、黑话、反讽 |
| **状态机跟踪** | 维护比赛完整状态流转，避免单句误判 |
| **置信度复核** | 低置信度自动触发外部裁判交叉验证 |

---

## 系统架构

```text
┌─────────────┐   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐
│  音频采集    │ → │  VAD 检测   │ → │  Whisper   │ → │  DeepSeek  │ → │   状态机     │ → │   执行动作   │
│pyaudiowpatch│   │ Silero VAD  │   │   medium   │   │    API     │   │     FSM    │   │  播放视频   │
└─────────────┘   └─────────────┘   └─────────────┘   └─────────────┘   └─────────────┘   └─────────────┘
     48kHz              16kHz             文字              语义            win/lose         安慰/结束
```

---

## 快速开始

### 环境要求

- Windows 10/11
- NVIDIA 显卡，支持 CUDA 12.6
- Python 3.12
- 麦克风/扬声器回环权限

### 安装依赖

```bash
# 1. 克隆仓库
git clone https://github.com/你的用户名/tes-ai-monitor.git
cd tes-ai-monitor

# 2. 创建虚拟环境
python -m venv venv
venv\Scripts\activate

# 3. 安装 PyTorch (CUDA 12.6)
pip install torch==2.12.1+cu126 torchaudio==2.11.0+cu126 --index-url https://download.pytorch.org/whl/cu126

# 如果官方下载慢，可以使用清华镜像，或从网盘下载本地 wheel 安装
# 详细方法见 SETUP.md

# 4. 安装其他依赖
pip install openai-whisper silero-vad pyaudiowpatch openai numpy==1.26.4
```

### 配置

```bash
copy config.example.py config.py
```

编辑 `config.py`，填入你的 DeepSeek API Key：

```python
TES_CONFIG = {
    'api_key': 'sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',
    'api_base': 'https://api.deepseek.com/v1',
    'model': 'deepseek-chat',
    ...
}
```

### 运行

```bash
python main_tes.py
```

然后播放任意 TES 比赛直播或回放，系统会自动监听并输出状态。

---

## 项目结构

```text
.
├── audio_capture.py      # 音频采集与重采样
├── vad_processor.py      # Silero VAD 人声检测
├── whisper_recognizer.py # Whisper 语音识别
├── tes_detector.py       # DeepSeek 语义推理 + 状态机
├── main_tes.py           # 主程序入口
├── config.example.py     # 配置模板
├── .gitignore            # Git 忽略规则
├── assets/               # 图片资源目录
│   ├── tes_logo.png
│   └── 视频封面.png
└── README.md             # 本文件
```

---

## 实时性优化

| 优化点 | 效果 |
|--------|------|
| 录音 chunk 1024 帧 | 采集延迟约 21ms |
| VAD 缓冲 512 样本 | 避免 "Input audio chunk is too short" 错误 |
| torchaudio 专业重采样 | 避免混叠失真，保护语音特征 |
| RTX 4060 CUDA 加速 | Whisper 推理压缩至 200ms 以内 |
| 异步 I/O 流水线 | 采集、推理、回传并行，消除阻塞 |

---

## 踩坑记录

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| torch 导入报 DLL 错误 | Anaconda Python VC++ 运行时版本不匹配 | 换用独立 Python 3.12 |
| Silero VAD 报 chunk too short | 重采样后样本数不足 512 | 录音 chunk 改为 1536，后优化为 1024 + 缓冲 |
| Whisper 跑得慢 | 默认使用 CPU | 设置 `device="auto"` 启用 CUDA |
| 检测到失败后连续打开多个网页 | 多线程重复触发 | 主线程加 `game_ended` 互斥标志 |
| PyCharm 检测不到解说 | 解释器选错导致 Silero 加载失败 | 切换为 `venv_new` 解释器 |

---

## Demo 视频

<p align="center">
  <a href="https://www.bilibili.com/video/BV1QdMF6VEYh/" target="_blank">
    <img src="./assets/视频封面.png" alt="Demo Video" width="640">
  </a>
  <br>
  <b>▶ 点击封面跳转到 B 站观看演示视频</b>
</p>

---

## 未来计划

- [ ] 支持同时监听多场比赛
- [ ] 接入弹幕/评论文本，实现多模态判断
- [ ] 打包成 Windows 桌面应用（PyInstaller / Nuitka）
- [ ] 增加赛后数据统计与回放分析
- [ ] 支持更多战队与游戏项目

---

## 技术栈

- [Python 3.12](https://www.python.org/)
- [PyTorch 2.12.1](https://pytorch.org/)
- [OpenAI Whisper](https://github.com/openai/whisper)
- [Silero VAD](https://github.com/snakers4/silero-vad)
- [DeepSeek API](https://platform.deepseek.com/)
- [pyaudiowpatch](https://github.com/s0d3s/PyAudioWPatch)

---

## 声明

本项目为个人技术学习与分享作品，仅供娱乐和交流使用。

比赛中使用的解说音频版权归原赛事主办方所有。

---

<p align="center">
  如果这个项目对你有帮助，欢迎 Star ⭐ 和 Fork 🍴
</p>
