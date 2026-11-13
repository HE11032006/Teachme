# Feuille de route technique : Tuteur d'anglais oral hors-ligne

> **Objectif global** : Construire un tuteur d'anglais oral interactif, 100 % local (sans GPU dédié, sur CPU i7-8665U), avec une latence de bout en bout < 2 secondes, capable de comprendre la parole spontanée (auto-corrections, hésitations) et d'adopter une posture pédagogique bienveillante (recast, encouragements, réponses courtes).

---

## 1. Capture Audio & Détection de Parole (VAD / Audio Input)
*Objectif : Réduire le temps mort entre la fin de phrase de l'utilisateur et le début du traitement.*

- [ ] **1.1. Optimisation du VAD (Voice Activity Detection)**
  - [ ] 1.1.1. Évaluer le VAD actuel par seuil d'énergie RMS (`audio.py`).
  - [ ] 1.1.2. Intégrer un VAD neuronal ultra-léger sur CPU (**Silero VAD**, latence < 1 ms).
  - [ ] 1.1.3. Ajuster la fenêtre de silence de fin de parole (passer de 1,5–2,0 s à 400–600 ms).
- [ ] **1.2. Gestion des bruits ambiants et artefacts**
  - [ ] 1.2.1. Calibration adaptative du bruit de fond au démarrage.
  - [ ] 1.2.2. Prévention des faux déclenchements (respiration, clics micro, bruits de frappe).
  - [ ] 1.2.3. Filtrage du retour audio (echo cancellation basique pour éviter que le micro ne réenregistre la voix du TTS).

---

## 2. Transcription Vocale Robuste (STT - Speech-to-Text)
*Objectif : Transcrire fidèlement ce que dit l'apprenant, y compris ses erreurs, en moins de 1,2 s.*

- [ ] **2.1. Calibrage et choix du modèle Whisper**
  - [ ] 2.1.1. Valider `faster-whisper` avec quantification `int8` sur CPU.
  - [ ] 2.1.2. Comparer `tiny.en` vs `base.en` (modèles dédiés anglais, plus précis et rapides que les multilingues).
  - [ ] 2.1.3. Fixer l'allocation CPU (`cpu_threads=4`) pour éviter la surcharge système.
- [ ] **2.2. Gestion des particularités de la parole apprenante**
  - [ ] 2.2.1. Filtrer les hallucinations Whisper sur le silence (`"thank you"`, `"thanks for watching"`, etc.).
  - [ ] 2.2.2. Désactiver la normalisation agressive de Whisper pour ne pas masquer les vraies erreurs grammaticales de l'élève.
  - [ ] 2.2.3. Tester la rétention des hésitations (*"uh"*, *"um"*, *"no"*).

---

## 3. Traitement des Reprises Vocales & Hésitations (*Speech Repair*)
*Objectif : Nettoyer la phrase tout en détectant si l'élève s'est corrigé tout seul.*

- [ ] **3.1. Module Python de détection des auto-corrections (`tutor/repair.py`)**
  - [ ] 3.1.1. Détection des marqueurs explicites de reprise (*"no"*, *"sorry"*, *"I mean"*, *"wait"*).
  - [ ] 3.1.2. Détection des répétitions de structures (ex: sujet + verbe incorrect suivi de sujet + verbe correct : *"she have... she has"*).
  - [ ] 3.1.3. Extraction du texte final nettoyé à destination du dialogue.
  - [ ] 3.1.4. Génération d'une métadonnée pédagogique (`self_corrected = True`, `old_part`, `new_part`).
- [ ] **3.2. Tests unitaires du module de réparation**
  - [ ] 3.2.1. Créer un banc de tests avec des phrases réelles d'apprenants A1/A2.
  - [ ] 3.2.2. Valider la non-régression sur des phrases fluides sans reprise.

---

## 4. Préparation des Données & Datasets (Hugging Face & Local)
*Objectif : Disposer d'un jeu de données de référence pour l'évaluation et le fine-tuning.*

- [ ] **4.1. Exploration et sélection des datasets ouverts sur Hugging Face**
  - [ ] 4.1.1. Datasets de disfluences et faux départs :
    - [ ] `amaai-lab/DisfluencySpeech` (corpus Switchboard avec annotations de réparations).
    - [ ] `hhoangphuoc/ami-disfluency`.
  - [ ] 4.1.2. Datasets de correction grammaticale (GEC) pour apprenants :
    - [ ] `agentlans/grammar-correction` (paires brut / corrigé).
    - [ ] `FCE` / Cambridge Learner Corpus (fautes réelles d'étudiants).
- [ ] **4.2. Construction du Dataset Tuteur (`dataset_tutor.jsonl`)**
  - [ ] 4.2.1. Définir le schéma d'apprentissage (Instruction / Contexte niveau / Entrée élève / Réponse tuteur).
  - [ ] 4.2.2. Automatiser la génération de paires avec reformulation pédagogique (*recast* + question courte).
  - [ ] 4.2.3. Intégrer les cas d'auto-correction avec félicitation explicite (*"Great self-correction!"*).
- [ ] **4.3. Stockage et exploitation des sessions locales**
  - [ ] 4.3.1. Faire évoluer le schéma SQLite (`storage.py`) pour logger :
    - Le texte brut issu de Whisper.
    - Le statut de reprise (`was_repaired`).
    - L'intention nettoyée et la réponse du tuteur.
  - [ ] 4.3.2. Écrire un script d'export `export_dataset.py` pour transformer l'historique utilisateur en données d'entraînement.

---

## 5. Cerveau Pédagogique & Fine-Tuning LLM
*Objectif : Obtenir un modèle ultra-rapide sur CPU, adoptant naturellement le rôle d'un tuteur bienveillant.*

- [ ] **5.1. Sélection de l'architecture du modèle de base**
  - [ ] 5.1.1. Privilégier les modèles compacts 1B à 3B paramètres :
    - **Llama 3.2 (1B et 3B)**
    - **Qwen 2.5 (1.5B et 3B)**
  - [ ] 5.1.2. Benchmark de vitesse brute en tokens/s sur le CPU cible via Ollama.
- [ ] **5.2. Stratégie de Fine-Tuning (LoRA / QLoRA)**
  - [ ] 5.2.1. Préparer l'environnement d'entraînement (Google Colab ou GPU distant avec Unsloth).
  - [ ] 5.2.2. Entraîner le modèle sur le dataset tuteur (style direct, < 20 mots, recast bienveillant, valorisation des auto-corrections).
  - [ ] 5.2.3. Évaluer la perte (*loss*) et la cohérence des réponses sur un ensemble de validation.
- [ ] **5.3. Quantification et déploiement local**
  - [ ] 5.3.1. Convertir les poids LoRA fusionnés au format **GGUF** (quantification `Q4_K_M` ou `Q4_0`).
  - [ ] 5.3.2. Créer le `Modelfile` pour intégration directe dans **Ollama** en local.
  - [ ] 5.3.3. Valider la consommation RAM (< 2 Go) et le temps de réponse (TTFT < 300 ms).

---

## 6. Synthèse Vocale Ultra-Rapide (TTS) & Streaming Audio
*Objectif : Faire entendre la voix du tuteur dès les premiers mots générés sans attendre la fin du texte.*

- [ ] **6.1. Sélection du moteur TTS local**
  - [ ] 6.1.1. Benchmark de **Piper TTS** (modèles ONNX ultra-rapides, voix anglaises naturelles, latence < 100 ms sur CPU).
  - [ ] 6.1.2. Évaluer en alternative le TTS natif Windows SAPI (0 ms mais voix plus métallique) ou Kokoro-82M.
- [ ] **6.2. Implémentation du pipeline en streaming (Cascade)**
  - [ ] 6.2.1. Découper le flux LLM en tokens / morceaux de phrase (dès qu'une virgule ou un point apparaît).
  - [ ] 6.2.2. Envoyer le premier tronçon de phrase au TTS pendant que le LLM génère la suite.
  - [ ] 6.2.3. Jouer l'audio de manière asynchrone sans bloquer la boucle principale.

---

## 7. Intégration Finale, Expérience Utilisateur & Métriques
*Objectif : Valider l'illusion d'une vraie conversation fluide et pédagogique.*

- [ ] **7.1. Orchestration dans `main.py`**
  - [ ] 7.1.1. Connecter l'ensemble : Micro $\rightarrow$ VAD $\rightarrow$ Whisper $\rightarrow$ Repair $\rightarrow$ LLM (Ollama) $\rightarrow$ TTS Streaming.
  - [ ] 7.1.2. Affichage temps réel dans le terminal des métriques de chaque tour (latence VAD, STT, LLM, TTS, totale).
- [ ] **7.2. Parcours pédagogiques structurés**
  - [ ] 7.2.1. Finaliser les modules thématiques A1/A2 (`courses/`).
  - [ ] 7.2.2. Mode conversation libre avec adaptation dynamique selon les réussites de l'élève.
- [ ] **7.3. Validation des critères de succès**
  - [ ] Latence globale mesurée < 2,0 s sur la machine hôte.
  - [ ] Traitement correct des reprises sans fausse alerte.
  - [ ] Zéro dépendance cloud (100 % opérationnel hors connexion réseau).

