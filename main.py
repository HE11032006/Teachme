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
HALLUCINATIONS = {"you", "thank you", "thanks for watching", "thank you for watching",
                  "bye", "the end"}


def show(reply):
    print(f"\nProf : {reply.text}")
    if reply.hint_fr:
        print(f"  Aide : {reply.hint_fr}")


def run_text(tutor):
    # Annonce des révisions dues (§Phase 3)
    due = tutor.get_due_reviews()
    if due:
        labels = [r.split(".")[-1].replace("_", " ") for r in due]
        print(f"\n📚 Révisions du jour : {', '.join(labels)}")

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

    # §4.6 : Bilan de fin de session (mode libre uniquement)
    summary = tutor.session_summary()
    if summary:
        print(f"\nProf (bilan) : {summary}")


def run_voice(tutor, cfg):
    from tutor.audio import calibrate_noise, record_utterance
    from tutor.stt import WhisperSTT
    from tutor.tts import make_tts

    print("Chargement de Whisper...")
    stt = WhisperSTT(cfg.whisper_model, cpu_threads=cfg.whisper_threads)
    tts = make_tts(cfg)

    print("Calibrage du micro : reste silencieux 1 seconde...")
    ambient = calibrate_noise(cfg.sample_rate, 1.0)
    threshold = max(cfg.energy_threshold, ambient * 3)
    print(f"Bruit ambiant : {ambient:.4f} | seuil de detection : {threshold:.4f}")

    # Annonce des révisions dues (§Phase 3)
    due = tutor.get_due_reviews()
    if due:
        labels = [r.split(".")[-1].replace("_", " ") for r in due]
        msg = f"Let's review something from last time first: {', '.join(labels)}."
        print(f"\nProf (révision) : {msg}")
        tts.speak(msg)

    reply = tutor.start()
    show(reply)
    tts.speak(reply.text)
    while not reply.finished:
        print("\n(Parle... Ctrl+C pour arreter)")
        time.sleep(0.3)  # laisse retomber l'echo de la voix avant d'ecouter
        audio = record_utterance(cfg.sample_rate, threshold,
                                 cfg.silence_seconds, cfg.hesitation_silence_seconds,
                                 cfg.max_record_seconds)
        if audio is None:
            print("(Je n'ai rien entendu)")
            continue

        t0 = time.time()
        heard = stt.transcribe(audio)
        t_stt = time.time() - t0
        text = heard.text
        stats = f"stt {t_stt:.1f} s | confiance {heard.logprob:.2f} | non-parole {heard.no_speech:.2f}"

        # §4.7 : Exploitation des signaux STT
        # Si confiance trop faible : ne pas évaluer comme faute, faire répéter gentiment
        low_confidence = heard.logprob < cfg.min_logprob
        # Si forte probabilité de non-parole / hésitation bloquée
        high_no_speech = heard.no_speech > cfg.max_no_speech
        hallucinated = text.lower().strip(" .!?") in HALLUCINATIONS

        if not text or hallucinated or low_confidence:
            print(f"(confiance faible : {text!r})  [{stats}]")
            reply = tutor.not_understood()
            show(reply)
            tts.speak(reply.text)
            continue

        if high_no_speech:
            print(f"(hesitation ou bruit détecté)  [{stats}]")
            # Propose un indice sans compter d'échec
            reply = tutor.not_understood()
            show(reply)
            tts.speak(reply.text)
            continue

        print(f"Toi (compris) : {text}")
        t0 = time.time()
        reply = tutor.reply(text, word_confidences=heard.word_confidences, stt_confidence=heard.logprob)
        t_llm = time.time() - t0
        show(reply)
        print(f"  [{stats} | llm {t_llm:.1f} s]")
        tts.speak(reply.text)

    # §4.6 : Bilan de fin de session (mode libre uniquement)
    summary = tutor.session_summary()
    if summary:
        print(f"\nProf (bilan) : {summary}")
        tts.speak(summary)


def main():
    parser = argparse.ArgumentParser(description="Tuteur d'anglais oral hors-ligne")
    parser.add_argument("--course", default="se_presenter", help="nom du fichier dans courses/")
    parser.add_argument("--text", action="store_true", help="mode clavier (sans micro ni voix)")
    parser.add_argument("--model", default=None, help="modele Ollama (defaut : qwen3:1.7b)")
    parser.add_argument("--level", default=None, help="niveau force : A1, A2, B1...")
    parser.add_argument("--llm-reactions", action="store_true",
                        help="le LLM commente chaque reponse du parcours guide (plus lent)")
    parser.add_argument("--tts", choices=["auto", "piper", "pyttsx3"], default=None,
                        help="moteur de voix (defaut : auto = Piper puis voix Windows)")
    args = parser.parse_args()

    cfg = Config()
    if args.model:
        cfg.llm_model = args.model
    if args.llm_reactions:
        cfg.llm_reactions = True
    if args.tts:
        cfg.tts_engine = args.tts

    course = load_course(cfg.courses_dir / f"{args.course}.json")
    if args.level:
        course.level = args.level

    llm = OllamaLLM(cfg.llm_model, cfg.ollama_url, cfg.temperature)
    if not llm.available():
        print("ATTENTION : Ollama est injoignable. Le prof utilisera des phrases de secours.")
    elif course.mode == "free" or cfg.llm_reactions:
        print("Chargement du modele...")
        llm.warm_up()

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
