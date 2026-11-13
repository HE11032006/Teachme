"""Test rapide du moteur Piper TTS ONNX."""

import time
from tutor.config import Config
from tutor.tts import make_tts

def test_tts():
    cfg = Config()
    cfg.tts_engine = "piper"
    print("Initialisation du TTS...")
    t0 = time.time()
    tts = make_tts(cfg)
    t_init = time.time() - t0
    print(f"Moteur charge en {t_init:.2f} s")

    phrase = "Hello! I am your local English tutor. Let's practice speaking English together!"
    print(f"\nLecture de la phrase : \"{phrase}\"")
    t0 = time.time()
    tts.speak(phrase)
    t_speak = time.time() - t0
    print(f"Temps total de generation et lecture : {t_speak:.2f} s")

if __name__ == "__main__":
    test_tts()

