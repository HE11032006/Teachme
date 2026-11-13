"""Synthese vocale.

Premiere version : pyttsx3 (voix Windows integrees, hors-ligne, qualite moyenne).
Pour une meilleure voix, on ajoutera Piper derriere la meme interface speak(text).
"""


class ConsoleTTS:
    """Mode sans voix : n'affiche rien de plus (le texte est deja affiche)."""

    def speak(self, text):
        pass


class Pyttsx3TTS:
    def __init__(self, rate=140):
        import pyttsx3
        self.engine = pyttsx3.init()
        self.engine.setProperty("rate", rate)
        for voice in self.engine.getProperty("voices"):
            if "english" in voice.name.lower():
                self.engine.setProperty("voice", voice.id)
                break

    def speak(self, text):
        self.engine.say(text)
        self.engine.runAndWait()


def make_tts(rate=140):
    try:
        return Pyttsx3TTS(rate)
    except Exception as e:  # pyttsx3 absent ou voix indisponible
        print(f"(Voix indisponible : {e}. Le prof repondra par ecrit seulement.)")
        return ConsoleTTS()
