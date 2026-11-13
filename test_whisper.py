'''
Test de reconnaissance vocale : Whisper tiny / base / small sur CPU.

    pip install faster-whisper sounddevice numpy
'''

import re
import time

import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel

SR = 16000          # frequence attendue par Whisper
SECONDS = 6         # duree d'enregistrement par phrase
MODELS = ["tiny", "base", "small"]
SENTENCES = [
    "Hello, how are you today?",
    "I would like a cup of coffee, please.",
    "Where is the nearest train station?",
    "I work on computers and I like to learn new things.",
    "Can you repeat that more slowly, please?",
]


def record(seconds=SECONDS):
    audio = sd.rec(int(seconds * SR), samplerate=SR, channels=1, dtype="float32")
    sd.wait()
    return audio[:, 0]


def words(text):
    return re.sub(r"[^a-z' ]", "", text.lower()).split()


def wer(ref, hyp):
    """Taux d'erreur de mots (distance de Levenshtein sur les mots)."""
    r, h = words(ref), words(hyp)
    d = list(range(len(h) + 1))
    for i in range(1, len(r) + 1):
        prev, d[0] = d[0], i
        for j in range(1, len(h) + 1):
            cur = d[j]
            d[j] = min(d[j] + 1, d[j - 1] + 1, prev + (r[i - 1] != h[j - 1]))
            prev = cur
    return d[len(h)] / max(len(r), 1)


def main():
    recordings = []
    for sentence in SENTENCES:
        input(f"\nPhrase : {sentence}\nAppuie sur Entree, puis lis-la a voix haute... ")
        print("Enregistrement...")
        recordings.append(record())

    summary = []
    for name in MODELS:
        print(f"\n=== Modele : {name} ===")
        t0 = time.time()
        model = WhisperModel(name, device="cpu", compute_type="int8")
        load_time = time.time() - t0

        total_time, scores = 0.0, []
        for ref, audio in zip(SENTENCES, recordings):
            t0 = time.time()
            segments, _ = model.transcribe(audio, language="en", beam_size=1)
            hyp = " ".join(s.text for s in segments).strip()
            dt = time.time() - t0
            score = wer(ref, hyp)
            total_time += dt
            scores.append(score)
            print(f"  attendu : {ref}\n  compris : {hyp}\n  WER {score:.0%}  |  {dt:.2f} s")

        summary.append((name, load_time, total_time / len(SENTENCES), float(np.mean(scores))))

    print("\n=== Resume (a copier dans NOTES.md) ===")
    print("| Modele | Chargement (s) | Transcription moy. (s) | WER moyen |")
    print("|---|---|---|---|")
    for name, load, avg, w in summary:
        print(f"| {name} | {load:.1f} | {avg:.2f} | {w:.0%} |")


if __name__ == "__main__":
    main()
