# %% [markdown]
# # Fine-Tuning du Tuteur d'Anglais Oral avec Unsloth (LoRA)
# 
# Ce notebook entraîne un modèle compact (**Llama-3.2-1B-Instruct** ou **Qwen2.5-1.5B-Instruct**) 
# pour adopter le comportement d'un tuteur d'anglais oral interactif et bienveillant.
# 
# **Temps estimé** : ~10-15 minutes sur un GPU T4 gratuit Google Colab.
# **Sortie** : Fichier quantifié `.gguf` prêt pour Ollama.

# %%
# 1. Installation des dépendances ultra-rapides Unsloth
!pip install --no-deps "xformers<0.0.29" "trl<0.9.0" peft accelerate bitsandbytes
!pip install "unsloth[colab-new] @ git+https://github.com/unslothai/unsloth.git"

# %%
# 2. Chargement du modèle de base avec quantification 4-bit (empreinte minimale)
from unsloth import FastLanguageModel
import torch

max_seq_length = 512
dtype = None # Auto detection
load_in_4bit = True

# Tu peux choisir "unsloth/Qwen2.5-1.5B-Instruct" ou "unsloth/Llama-3.2-1B-Instruct"
model_name = "unsloth/Qwen2.5-1.5B-Instruct"

model, tokenizer = FastLanguageModel.from_pretrained(
    model_name = model_name,
    max_seq_length = max_seq_length,
    dtype = dtype,
    load_in_4bit = load_in_4bit,
)

# %%
# 3. Configuration LoRA (Adapteurs légers)
model = FastLanguageModel.get_peft_model(
    model,
    r = 16, # Rang LoRA
    target_modules = ["q_proj", "k_proj", "v_proj", "o_proj",
                      "gate_proj", "up_proj", "down_proj"],
    lora_alpha = 16,
    lora_dropout = 0,
    bias = "none",
    use_gradient_checkpointing = "unsloth",
    random_state = 3407,
)

# %%
# 4. Chargement de ton dataset tutor_finetune.jsonl
# Uploade ton fichier 'tutor_finetune.jsonl' dans la barre latérale de Google Colab
from datasets import load_dataset

dataset = load_dataset("json", data_files="tutor_finetune.jsonl", split="train")

def formatting_prompts_func(examples):
    convs = examples["messages"]
    texts = [tokenizer.apply_chat_template(convo, tokenize=False, add_generation_prompt=False) for convo in convs]
    return { "text" : texts }

dataset = dataset.map(formatting_prompts_func, batched = True)

# %%
# 5. Entraînement avec SFTTrainer
from trl import SFTTrainer
from transformers import TrainingArguments
from unsloth import is_bfloat16_supported

trainer = SFTTrainer(
    model = model,
    tokenizer = tokenizer,
    train_dataset = dataset,
    dataset_text_field = "text",
    max_seq_length = max_seq_length,
    dataset_num_proc = 2,
    packing = False,
    args = TrainingArguments(
        per_device_train_batch_size = 4,
        gradient_accumulation_steps = 4,
        warmup_steps = 10,
        max_steps = 120, # Suffisant pour 1500 exemples en LoRA
        learning_rate = 2e-4,
        fp16 = not is_bfloat16_supported(),
        bf16 = is_bfloat16_supported(),
        logging_steps = 10,
        optim = "adamw_8bit",
        weight_decay = 0.01,
        lr_scheduler_type = "linear",
        seed = 3407,
        output_dir = "outputs",
    ),
)

trainer_stats = trainer.train()

# %%
# 6. Export direct en GGUF pour Ollama (Quantification Q4_K_M)
# Cela génère un fichier 'tutor-model-q4_k_m.gguf' directement téléchargeable
model.save_pretrained_gguf("tutor_model_gguf", tokenizer, quantization_method = "q4_k_m")

print("Félicitations ! Le modèle est exporté en GGUF. Télécharge-le pour l'importer dans Ollama.")

