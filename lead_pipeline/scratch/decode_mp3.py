import subprocess
import sys
from pathlib import Path
import static_ffmpeg

# This downloads/configures the static ffmpeg path on the first call
static_ffmpeg.add_paths()

def convert_mp3_to_wav(mp3_path: Path, wav_path: Path):
    print(f"Decoding via FFmpeg: {mp3_path.name} -> {wav_path.name}...")
    try:
        # ffmpeg -y (overwrite) -i input.mp3 output.wav
        cmd = ["ffmpeg", "-y", "-i", str(mp3_path), str(wav_path)]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if res.returncode == 0:
            print("  Decoding successful!")
            return True
        else:
            print(f"  FFmpeg error for {mp3_path.name}:\n{res.stderr}")
            return False
    except Exception as e:
        print(f"  Exception decoding {mp3_path.name}: {e}")
        return False

if __name__ == "__main__":
    user_uploaded_dir = Path("C:/Users/Kaivalya/.gemini/antigravity/brain/bcc3d2fa-d475-4775-83f4-b224c5bccbd1/.user_uploaded")
    scratch_dir = Path("C:/Users/Kaivalya/.gemini/antigravity/brain/bcc3d2fa-d475-4775-83f4-b224c5bccbd1/scratch")
    scratch_dir.mkdir(parents=True, exist_ok=True)
    
    mp3_files = list(user_uploaded_dir.glob("*.mp3"))
    if not mp3_files:
        print("No MP3 files found in user_uploaded directory.")
        sys.exit(1)
        
    for mp3_f in mp3_files:
        wav_f = scratch_dir / (mp3_f.stem + ".wav")
        convert_mp3_to_wav(mp3_f, wav_f)
