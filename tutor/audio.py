"""Entree micro avec detection simple de fin de phrase (energie sonore).

C'est un detecteur volontairement basique : il marche bien dans une piece calme.
Le seuil est calibre sur le bruit ambiant au demarrage.
"""

import numpy as np
import sounddevice as sd


def calibrate_noise(sample_rate=16000, seconds=1.0):
    """Mesure le bruit ambiant (niveau RMS) pendant quelques instants de silence."""
    audio = sd.rec(int(seconds * sample_rate), samplerate=sample_rate,
                   channels=1, dtype="float32")
    sd.wait()
    return float(np.sqrt(np.mean(audio ** 2)))


def record_utterance(sample_rate=16000, threshold=0.01, silence_seconds=0.8,
                     hesitation_silence_seconds=1.4, max_seconds=15.0,
                     block_ms=30, min_loud_blocks=6):
    """Attend que la personne parle, enregistre, s'arrete apres un silence adaptatif.

    - silence_seconds (defaut 0.8s) : declenche la coupure rapide quand une phrase
      consistante est deja prononcee.
    - hesitation_silence_seconds (defaut 1.4s) : donne du temps supplementaire a l'apprenant
      s'il vient tout juste d'emettre 1 ou 2 mots et cherche la suite.

    Retourne un tableau numpy float32 (mono), ou None si rien n'a ete entendu.
    """
    block = int(sample_rate * block_ms / 1000)
    max_blocks = int(max_seconds * 1000 / block_ms)

    chunks, pre = [], []
    started = False
    silent = 0
    loud_blocks = 0

    with sd.InputStream(samplerate=sample_rate, channels=1, dtype="float32",
                        blocksize=block) as stream:
        for _ in range(max_blocks):
            data, _overflow = stream.read(block)
            data = data[:, 0]
            loud = float(np.sqrt(np.mean(data ** 2))) > threshold

            if not started:
                pre.append(data)
                pre = pre[-10:]          # garde un peu d'audio avant le debut
                if loud:
                    started = True
                    loud_blocks = 1
                    chunks.extend(pre)
                    silent = 0
                continue

            chunks.append(data)
            if loud:
                loud_blocks += 1
                silent = 0
            else:
                silent += 1

            # Silence adaptatif : plus tolérant au debut de la phrase (hesitation),
            # plus reactif et court une fois la phrase bien entamee (> 15 blocs de parole).
            active_silence = (
                silence_seconds if loud_blocks >= 15 else hesitation_silence_seconds
            )
            max_silent = int(active_silence * 1000 / block_ms)

            if silent >= max_silent:
                break

    if not chunks or loud_blocks < min_loud_blocks:
        return None
    return np.concatenate(chunks)
