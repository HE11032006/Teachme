"""Point d'entree du tuteur.

Exemples :
    python main.py --text                       # clavier, pour tester la logique
    python main.py                              # voix (micro + Whisper + voix)
    python main.py --course libre               # conversation libre
    python main.py --course se_presenter --level A2
"""

import argparse
import time

from tutor.config import Config
from tutor.course import load_course
from tutor.llm import OllamaLLM
from tutor.session import Tutor
from tutor.storage import Store

# Phrases que Whisper "invente" parfois sur du silence ou du bruit
HALLUCINATIONS = {"you", "thank you", "thanks for watching", "bye"}


def show(reply):
    print(f"\nProf : {reply.text}")
    if reply.hint_fr:
        print(f"  Aide : {reply.hint_fr}")


def run_text(tutor):
    reply = tutor.start()
    show(reply)
    while not reply.finished:
        try:
            text = input("\nToi : ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if text.lower() in {"quit", "exit", "q"}:
            break
        if not text:
            continue
        t0 = time.time()
        reply = tutor.reply(text)
        show(reply)
        print(f"  [llm {time.time() - t0:.1f} s]")


def run_voice(tutor, cfg):
    from tutor.audio import record_utterance
    from tutor.stt import WhisperSTT
    from tutor.tts import make_tts

    print("Chargement de Whisper...")
    stt = WhisperSTT(cfg.whisper_model)
    tts = make_tts(cfg.speech_rate)

    reply = tutor.start()
    show(reply)
    tts.speak(reply.text)
    while not reply.finished:
        print("\n(Parle... Ctrl+C pour arreter)")
        audio = record_utterance(cfg.sample_rate, cfg.energy_threshold,
                                 cfg.silence_seconds, cfg.max_record_seconds)
        if audio is None:
            print("(Je n'ai rien entendu)")
            continue
        t0 = time.time()
        text = stt.transcribe(audio)
        t_stt = time.time() - t0
        if not text or text.lower().strip(" .!?") in HALLUCINATIONS:
            print("(Pas compris, repete s'il te plait)")
            continue
        print(f"Toi (compris) : {text}")
        t0 = time.time()
        reply = tutor.reply(text)
        t_llm = time.time() - t0
        show(reply)
        tts.speak(reply.text)
        print(f"  [stt {t_stt:.1f} s | llm {t_llm:.1f} s]")


def main():
    parser = argparse.ArgumentParser(description="Tuteur d'anglais oral hors-ligne")
    parser.add_argument("--course", default="se_presenter", help="nom du fichier dans courses/")
    parser.add_argument("--text", action="store_true", help="mode clavier (sans micro ni voix)")
    parser.add_argument("--model", default=None, help="modele Ollama (defaut : qwen3:1.7b)")
    parser.add_argument("--level", default=None, help="niveau force : A1, A2, B1...")
    args = parser.parse_args()

    cfg = Config()
    if args.model:
        cfg.llm_model = args.model

    course = load_course(cfg.courses_dir / f"{args.course}.json")
    if args.level:
        course.level = args.level

    llm = OllamaLLM(cfg.llm_model, cfg.ollama_url, cfg.temperature)
    if not llm.available():
        print("ATTENTION : Ollama est injoignable. Le prof utilisera des phrases de secours.")

    store = Store(cfg.db_path)
    tutor = Tutor(course, llm, cfg, store)
    print(f"Parcours : {course.title} (niveau {course.level}) | modele : {cfg.llm_model}")
    try:
        if args.text:
            run_text(tutor)
        else:
            run_voice(tutor, cfg)
    except KeyboardInterrupt:
        pass
    finally:
        tutor.close()
        store.close()
        print("\nSession terminee.")


if __name__ == "__main__":
    main()
