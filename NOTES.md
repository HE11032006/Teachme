# Notes : tuteur d'anglais oral hors-ligne

## Machine de test

- Processeur : Intel Core i7-8665U (portable, 4 coeurs), 1,9 GHz
- RAM : 24 Go
- Carte graphique : Intel UHD 620 (integree, pas de GPU dedie) : tout tourne sur CPU
- Systeme : Windows 64 bits

## Test 1 : reconnaissance vocale (Whisper, faster-whisper, int8, CPU)

Script : `test_whisper.py` (5 phrases simples lues a voix haute, 6 s par phrase).

| Modele | Chargement (s) | Transcription moy. (s) | WER moyen |
|---|---|---|---|
| tiny | 21.8 | 1.20 | 8% |
| base | 38.1 | 1.89 | 10% |
| small | 88.3 | 5.76 | 0% |

**Lecture des resultats**
- Les temps de chargement incluent le telechargement des modeles au premier lancement : a relancer pour avoir les vrais temps.
- `small` comprend tout mais prend environ 5,8 s pour un clip de 6 s : trop lent pour une conversation (objectif : moins de 2 s de latence totale).
- `tiny` et `base` sont utilisables. Leur ecart de WER n'est pas significatif sur 5 phrases.
- Limites du test : phrases simples et lues (pas de parole spontanee), une seule session, 5 phrases seulement.

**Decision provisoire** : developper avec `tiny`.

**A tester ensuite**
- Modeles anglais seul (`tiny.en`, `base.en`) et `distil-small.en`.
- Un test plus grand (15 a 20 phrases) avec de la parole spontanee et un peu de bruit.

## Test 2 : petit LLM (Ollama, CPU)

Script : `test_llm.py`. A lancer : `python test_llm.py modele1 modele2`.

| Modele | Prompt moy. (s) | Tokens/s | Mots moy. | Mots max |
|---|---|---|---|---|
| qwen3:1.7b | 0.38 | 17.3 | 15 | 19 |
| qwen2.5:0.5b | 0.13 | 49.2 | 13 | 20 |

**Criteres**
- Vitesse : au moins 8 a 10 tokens/s pour une conversation fluide.
- Reponses courtes : moins de 25 a 30 mots.
- Corrections justes (a faire relire par quelqu'un qui lit bien l'anglais).

## Objectifs de reference

- Latence de bout en bout : moins de 2 secondes.
- RAM utilisee : moins de 2 Go sur mobile (profil 6 Go).
- Niveau de depart du tuteur : A1 puis A2, avec aide en francais possible.
