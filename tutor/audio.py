"""Entree micro avec detection simple de fin de phrase (energie sonore).

C'est un detecteur volontairement basique : il marche bien dans une piece calme.
On pourra le remplacer par un vrai VAD (Silero) plus tard.
"""

import numpy as np
import sounddevice as sd


def record_utterance(sample_rate=16000, threshold=0.01, silence_seconds=1.0,
                     max_seconds=15.0, block_ms=30):
    """Attendre que la personne parle, enregistre, s'arrete apres un silence.

    Retourne un tableau numpy float32 (mono), ou None si rien n'a ete entendu.
    """
    block = int(sample_rate * block_ms / 1000)
    max_blocks = int(max_seconds * 1000 / block_ms)
    max_silent = int(silence_seconds * 1000 / block_ms)

    chunks, pre = [], []
    started = False
    silent = 0

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
                    chunks.extend(pre)
                    silent = 0
                continue

            chunks.append(data)
            silent = 0 if loud else silent + 1
            if silent >= max_silent:
                break

    if not chunks:
        return None
    return np.concatenate(chunks)
