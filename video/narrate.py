"""Adds the bottom-right narration to the recorded terminal run: terminal.mp4 -> terminal_narrated.mp4.

    python3 narrate.py      (after node stills.js has rendered frames/tcap*.png)

Times match what the recorded run shows on screen.
"""
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
CAPS = [("tcap1", 0.4, 3.0), ("tcap2", 3.3, 11.8), ("tcap3", 12.1, 14.5),
        ("tcap4", 14.8, 22.8), ("tcap5", 23.1, 26.5), ("tcap6", 26.8, 31.0)]

args, fc, prev = ["-i", str(HERE / "terminal.mp4")], [], "[0:v]"
for i, (name, a, b) in enumerate(CAPS, start=1):
    args += ["-loop", "1", "-t", "31.1", "-i", str(HERE / "frames" / f"{name}.png")]
    fc.append(f"[{i}:v]format=rgba,fade=t=in:st={a}:d=0.3:alpha=1,fade=t=out:st={b - 0.3}:d=0.3:alpha=1[c{i}]")
    fc.append(f"{prev}[c{i}]overlay=0:0:enable='between(t,{a},{b})'[v{i}]")
    prev = f"[v{i}]"
fc.append(f"{prev}format=yuv420p[out]")
subprocess.run(["ffmpeg", "-v", "error", "-y", *args, "-filter_complex", ";".join(fc), "-map", "[out]",
                "-t", "31.04", "-c:v", "libx264", "-crf", "18", "-r", "30", str(HERE / "terminal_narrated.mp4")], check=True)
print("wrote terminal_narrated.mp4")
