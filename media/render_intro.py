"""Render an evidence-bounded project introduction from actual UI screenshots.

Requires Pillow and FFmpeg. No generated robot footage, external music or TTS.
"""
from __future__ import annotations

import argparse
import array
import hashlib
import json
import math
from pathlib import Path
import subprocess
import wave

from PIL import Image, ImageDraw, ImageFont, ImageOps


ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "output"
BG = "#f5f7f7"
INK = "#172322"
MUTED = "#526260"
TEAL = "#007f73"
CORAL = "#cb493d"
FONT = None
SCENES = [
    (7, "OPEN SOURCE / ALPHA", "Open Embodied\nSimOps", "把分散的机器人实验组织起来", "A self-hosted robotics workflow workbench", "brand"),
    (8, "01 / CONFIGURE", "从一个任务配置开始", "场景 · 资产 · 机器人 · 任务 · 传感器", "Scenes, assets, robots, tasks and sensors", "generate"),
    (8, "02 / WORKFLOW DESIGN", "不是换引擎，是接起流程", "让现有工具有共同的任务与产物记录", "Connect existing tools through tasks and artifacts", "flow"),
    (8, "03 / DATASETS", "数据，应该能追溯", "检查、合并、转换，进入训练工作流", "Inspect, merge and convert data for training", "datasets"),
    (8, "04 / TRAINING", "训练，不该丢掉来路", "LeRobot 集成 · 配置、日志与产物", "LeRobot integration, configuration and artifacts", "training"),
    (8, "05 / PROVENANCE", "每个产物，都有记录", "来源、版本、许可证与 SHA-256", "Source, version, license and content hash", "provenance"),
    (9, "06 / SCOPE", "Alpha，不是生产承诺", "真实边界，是可复现的起点", "Transparent limitations before stronger claims", "scope"),
    (8, "BUILD IN THE OPEN", "一起把一条链路做扎实", "Apache-2.0 · 中文 / English", "Contribute reproducibility, adapters and acceptance tests", "end"),
]


def font(size):
    return ImageFont.truetype(str(FONT), size=size)


def text(draw, xy, value, size, color=INK, width=None, spacing=10):
    f = font(size)
    lines = []
    for line in value.splitlines():
        if width is None:
            lines.append(line)
            continue
        current = ""
        for char in line:
            if current and draw.textlength(current + char, font=f) > width:
                lines.append(current)
                current = ""
            current += char
        lines.append(current)
    y = xy[1]
    for line in lines:
        draw.text((xy[0], y), line, font=f, fill=color)
        y += size + spacing
    return y


def slide(scene, portrait):
    duration, eyebrow, title, sub, en, kind = scene
    w, h = (1080, 1920) if portrait else (1920, 1080)
    im = Image.new("RGB", (w, h), BG)
    d = ImageDraw.Draw(im)
    m = 72
    d.rectangle((m, 70, m + 8, 117), fill=TEAL)
    text(d, (m + 28, 76), eyebrow, 26, TEAL)
    text(d, (w - 180, 76), "ALPHA", 24, CORAL)
    if kind == "brand":
        text(d, (m, 225 if portrait else 150), title, 100 if portrait else 132, width=w - 2*m, spacing=12)
        text(d, (m, 530 if portrait else 470), sub, 48 if portrait else 54, width=w-2*m)
        text(d, (m, 650 if portrait else 555), en, 28 if portrait else 34, MUTED, width=w-2*m)
        y = 910 if portrait else 740
        labels = ["SIMULATION", "DATA", "POLICY"]
        for idx, label in enumerate(labels):
            xx = m if portrait else m + idx * 575
            yy = y + idx*150 if portrait else y
            d.line((xx, yy, xx + (w-2*m if portrait else 500), yy), fill=TEAL, width=3)
            text(d, (xx, yy+25), label, 44)
        text(d, (m, h-265 if portrait else h-185), "自托管工作台 / 原创代码 Apache-2.0", 26, MUTED)
    else:
        title_bottom = text(d, (m, 170), title, 61 if portrait else 70, width=w-2*m)
        text(d, (m, title_bottom+20), sub, 32 if portrait else 36, width=w-2*m)
        text(d, (m, title_bottom+85), en, 25 if portrait else 29, MUTED, width=w-2*m)
        top = 550 if portrait else 410
        if kind in {"generate", "datasets", "training"}:
            source = Image.open(OUTPUT / "source" / f"{kind}.jpg").convert("RGB")
            # Portrait uses a visible crop of the same screenshot, never a fabricated UI.
            if portrait:
                source = source.crop((280, 0, min(source.width, 1400), source.height))
            maxsize = (w-2*m, 880 if portrait else 490)
            source = ImageOps.contain(source, maxsize)
            im.paste(source, (m, top))
            d.rectangle((m, top, m+source.width, top+source.height), outline="#c9d5d1", width=2)
            note_y = top + source.height + 28
            text(d, (m, note_y), "实际本地工作台 · 尚未运行 GPU 任务", 26, TEAL, width=w-2*m)
            text(d, (m, note_y+52), "Actual local UI; no GPU run demonstrated", 24, MUTED, width=w-2*m)
        elif kind == "flow":
            labels = [("场景 / 资产", "Scene & assets"), ("仿真 / 采集", "Simulation & data"), ("转换 / 训练", "Conversion & training"), ("评测 / 接口", "Evaluation & export")]
            for idx, (zh, english) in enumerate(labels):
                xx = m if portrait else m+idx*445
                yy = top+idx*195 if portrait else top+55
                d.line((xx, yy, xx+(w-2*m if portrait else 370), yy), fill=TEAL if idx%2==0 else CORAL, width=4)
                text(d, (xx, yy+28), f"0{idx+1}", 30, TEAL)
                text(d, (xx+90 if portrait else xx, yy+26 if portrait else yy+95), zh, 42)
                text(d, (xx+90 if portrait else xx, yy+94 if portrait else yy+165), english, 24, MUTED)
            text(d, (m, 1460 if portrait else 825), "工作流设计示意；各适配器完成度不同", 27, MUTED, width=w-2*m)
            text(d, (m, 1515 if portrait else 880), "Workflow design; integration status varies", 24, MUTED, width=w-2*m)
        elif kind == "provenance":
            fields = [("source.uri", "来源"), ("source.version", "版本"), ("source.license", "许可声明"), ("sha256", "内容指纹")]
            for idx, (key, label) in enumerate(fields):
                yy = top+idx*(160 if portrait else 104)
                d.line((m, yy, w-m, yy), fill="#c9d5d1", width=2)
                text(d, (m, yy+24), key, 44 if portrait else 40, TEAL)
                text(d, (w-310, yy+28), label, 32)
            text(d, (m, 1370 if portrait else 875), "字段示意，不展示虚构哈希或实验结果", 27, MUTED, width=w-2*m)
        elif kind == "scope":
            lines = ["已实现：配置、执行、来源记录", "待完善：原生窗口与会话统一", "待复验：GPU 完整闭环", "未验收：真实机器人部署"]
            ens = ["Task execution and artifact tracking", "Shared native-viewer and bridge state", "Fresh full GPU acceptance", "Physical-robot deployment"]
            for idx, line in enumerate(lines):
                yy = top+idx*(205 if portrait else 114)
                text(d, (m, yy), line, 37 if portrait else 40, TEAL if idx==0 else INK, width=w-2*m)
                text(d, (m, yy+65), ens[idx], 25, MUTED, width=w-2*m)
        elif kind == "end":
            text(d, (m, top+35), "GitHub", 58, TEAL)
            text(d, (m, top+145), "eust-w/", 48)
            text(d, (m, top+220), "open-embodied-simops", 56 if portrait else 88, width=w-2*m)
            text(d, (m, top+405), "复现一个任务。补齐一份证据。", 38, width=w-2*m)
            text(d, (m, top+480), "Reproduce a task. Contribute the evidence.", 27, MUTED, width=w-2*m)
    d.line((m, h-130, w-m, h-130), fill="#c9d5d1", width=2)
    text(d, (m, h-105), "项目介绍 / 非仿真效果演示", 23, MUTED)
    text(d, (m, h-66), "Project introduction, not a simulator execution demo", 20, MUTED)
    return im


def soundtrack(path, duration):
    rate = 48000
    data = array.array("h")
    # Original quiet synthesized tones, not sampled music or a cloned voice.
    notes = (220.0, 261.63, 329.63, 293.66)
    for i in range(int(rate*duration)):
        t = i/rate
        phase = t % 1.0
        env = math.exp(-phase*9)*min(1.0, phase*150)
        f = notes[int(t/4)%len(notes)]
        tone = (math.sin(2*math.pi*f*t)+0.35*math.sin(2*math.pi*f*2*t))*env*0.065
        fade = min(1.0, t/1.5, (duration-t)/2.0)
        data.append(int(tone*fade*32767))
    with wave.open(str(path), "wb") as wav:
        wav.setparams((1, 2, rate, 0, "NONE", "not compressed"))
        wav.writeframes(data.tobytes())


def srt_time(seconds):
    ms = int(seconds*1000)
    return f"{ms//3600000:02}:{ms//60000%60:02}:{ms//1000%60:02},{ms%1000:03}"


def render(portrait):
    label = "vertical" if portrait else "landscape"
    parts = []
    for idx, scene in enumerate(SCENES):
        still = OUTPUT / f"{label}-{idx:02}.png"
        clip = OUTPUT / f"{label}-{idx:02}.mp4"
        slide(scene, portrait).save(still)
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-loop", "1", "-i", str(still), "-t", str(scene[0]), "-vf", "fade=t=in:st=0:d=0.2", "-r", "30", "-c:v", "libx264", "-preset", "fast", "-crf", "20", "-pix_fmt", "yuv420p", str(clip)], check=True)
        parts.append(clip)
    concat = OUTPUT / f"{label}-concat.txt"
    concat.write_text("\n".join(f"file '{p.name}'" for p in parts)+"\n")
    dest = OUTPUT / f"simops-intro-{label}.mp4"
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(concat), "-i", str(OUTPUT / "original-tone.wav"), "-c:v", "copy", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", "-shortest", str(dest)], check=True)
    slide(SCENES[0], portrait).save(OUTPUT / f"cover-{label}.jpg", quality=94)
    return {"file": dest.name, "sha256": hashlib.sha256(dest.read_bytes()).hexdigest(), "duration": sum(s[0] for s in SCENES)}


def main():
    global FONT
    parser = argparse.ArgumentParser()
    parser.add_argument("--font", type=Path, required=True, help="Locally installed CJK font; not redistributed")
    args = parser.parse_args()
    FONT = args.font
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for source in ("generate", "datasets", "training"):
        if not (OUTPUT / "source" / f"{source}.jpg").is_file():
            raise SystemExit(f"Missing actual UI capture: {source}.jpg")
    soundtrack(OUTPUT / "original-tone.wav", sum(s[0] for s in SCENES))
    captions = {"zh": [], "en": []}
    start = 0
    for idx, scene in enumerate(SCENES):
        for lang, caption in (("zh", scene[2].replace("\n", " ")+"\n"+scene[3]), ("en", scene[4])):
            captions[lang].append(f"{idx+1}\n{srt_time(start)} --> {srt_time(start+scene[0])}\n{caption}\n")
        start += scene[0]
    for lang, values in captions.items():
        (OUTPUT / f"intro.{lang}.srt").write_text("\n".join(values), encoding="utf-8")
    files = [render(False), render(True)]
    (OUTPUT / "manifest.json").write_text(json.dumps({"kind":"project-introduction-not-runtime-demo", "audio":"original synthesized tones; no narration", "sources":"actual local UI screenshots and original diagrams", "files":files}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(files, indent=2))


if __name__ == "__main__":
    main()
