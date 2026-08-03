"""使用 faster-whisper large-v3 进行中文语音转文字"""
import json, time
from pathlib import Path
from faster_whisper import WhisperModel

AUDIO_DIR = Path(r"g:\理财\个股分析\SZ.002714 牧原股份\data\bilibili_videos")
OUTPUT_DIR = AUDIO_DIR / "transcripts"
OUTPUT_DIR.mkdir(exist_ok=True)

FILES = sorted(AUDIO_DIR.glob("*.m4a")) + sorted(AUDIO_DIR.glob("*.mp3"))
print(f"找到 {len(FILES)} 个音频文件\n")

print("加载 small 模型（快速模式，~6x 实时速度）...")
model = WhisperModel("small", device="cpu", compute_type="int8")
print("模型就绪\n")

for f in FILES:
    out_txt = OUTPUT_DIR / f"{f.stem}.txt"
    out_json = OUTPUT_DIR / f"{f.stem}.json"

    if out_txt.exists() and out_txt.stat().st_size > 100:
        print(f"  ⏭ 跳过（已存在）: {f.name}")
        continue

    size_mb = f.stat().st_size / 1024 / 1024
    print(f"🎤 转录: {f.name} ({size_mb:.1f} MB)")
    t0 = time.time()

    segments_result, info = model.transcribe(
        str(f),
        beam_size=5,
        language="zh",
        vad_filter=True,
        vad_parameters=dict(min_silence_duration_ms=500),
    )

    segments = []
    full_text_parts = []
    seg_count = 0
    for seg in segments_result:
        segments.append({
            "start": round(seg.start, 2),
            "end": round(seg.end, 2),
            "text": seg.text.strip(),
        })
        full_text_parts.append(seg.text.strip())
        seg_count += 1

    full_text = "".join(full_text_parts)

    out_txt.write_text(full_text if full_text else "(无识别结果)", encoding="utf-8")
    out_json.write_text(json.dumps(segments, ensure_ascii=False, indent=2), encoding="utf-8")

    elapsed = time.time() - t0
    words = len(full_text)
    avg = elapsed / seg_count if seg_count > 0 else 0
    print(f"  ✅ 完成: {words} 字, {seg_count} 句, 耗时 {elapsed/60:.1f} 分钟 ({avg:.1f}s/段)\n")

print(f"✅ 全部完成！输出: {OUTPUT_DIR}")
