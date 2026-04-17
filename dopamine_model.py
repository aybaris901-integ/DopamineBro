# train_model_improved.py
import random
from setfit import SetFitModel, Trainer, TrainingArguments
from datasets import Dataset
from sklearn.preprocessing import LabelEncoder
from transformers import pipeline  # для аугментации (опционально)

# ------------------- 1. Расширяем датасет вручную + аугментация -------------------

base_examples = {
    "Self-validation": [
        "am I smart", "I might be smart", "do I have potential", "I think I'm clever",
        "am I good enough for myself", "is my self-worth okay", "I feel competent today"
    ],
    "Unearned praise": [
        "tell me I'm awesome", "say I'm the best", "you should praise me",
        "I deserve a compliment", "tell me I'm perfect", "call me brilliant"
    ],
    "Validation fishing": [
        "is my code impressive", "do you think I'm talented", "am I better than John",
        "is my design cool", "don't you agree I'm good", "would you say I'm skilled"
    ],
    "Praise request": [
        "compliment my hair", "say something nice about me", "give me a compliment",
        "tell me something positive about me", "say I'm beautiful", "tell me I look great"
    ],
    "Comparison trap": [
        "am I better than John", "am I smarter than my friends", "do I beat others",
        "am I the best in the room", "compared to him, am I good"
    ],
    "Looks validation": [
        "do I look good", "am I attractive", "is my appearance nice",
        "tell me I'm pretty", "do you like my face"
    ],
    "Age validation": [
        "for a 15-year-old", "am I mature for my age", "is that good for a teenager",
        "for someone my age, am I doing well"
    ],
    "Desperate validation": [
        "validate me please", "please say I'm okay", "I need you to confirm I'm good",
        "just tell me I'm not bad", "I'm begging for a compliment"
    ]
}

# Функция аугментации: синонимическая замена (упрощённо, без внешних библиотек)
synonyms = {
    "smart": ["intelligent", "clever", "bright", "sharp"],
    "good": ["great", "fine", "nice", "decent"],
    "awesome": ["amazing", "fantastic", "incredible"],
    "beautiful": ["gorgeous", "lovely", "stunning"],
    "talented": ["gifted", "skilled", "capable"],
    "code": ["program", "script", "project"],
    "design": ["layout", "style", "look"]
}

def augment_text(text, n=2):
    """Создаёт n вариаций текста с заменой слов."""
    augmented = []
    words = text.split()
    for _ in range(n):
        new_words = []
        for w in words:
            if w.lower() in synonyms and random.random() > 0.5:
                new_words.append(random.choice(synonyms[w.lower()]))
            else:
                new_words.append(w)
        augmented.append(" ".join(new_words))
    return augmented

# Генерируем финальный датасет
texts = []
labels = []

for label, phrases in base_examples.items():
    for phrase in phrases:
        texts.append(phrase)
        labels.append(label)
        # Добавляем 2 аугментированные версии
        for aug_phrase in augment_text(phrase, n=2):
            texts.append(aug_phrase)
            labels.append(label)

# ------------------- 2. Преобразуем метки в числа -------------------
le = LabelEncoder()
numeric_labels = le.fit_transform(labels)  # теперь 0,1,2,...

# ------------------- 3. Создаём Dataset и обучаем -------------------
dataset = Dataset.from_dict({"text": texts, "label": numeric_labels})

# Покажем статистику
print(f"Всего примеров: {len(texts)}")
print(f"Классы: {dict(zip(le.classes_, range(len(le.classes_))))}")
print("Распределение:")
for i, cls in enumerate(le.classes_):
    count = sum(1 for l in numeric_labels if l == i)
    print(f"  {cls}: {count}")

# Модель (можно взять меньшую для скорости, например, 'all-MiniLM-L6-v2')
model = SetFitModel.from_pretrained("sentence-transformers/paraphrase-mpnet-base-v2")

# Аргументы обучения (добавим эпохи, batch_size)
args = TrainingArguments(
    batch_size=16,
    num_epochs=8,           # больше эпох, т.к. данных стало больше
    evaluation_strategy="epoch",  # если есть валидация
    save_strategy="epoch",
    load_best_model_at_end=True,
)

# Разделим на train/val (80/20) для честной оценки
split_dataset = dataset.train_test_split(test_size=0.2, seed=42)
train_dataset = split_dataset["train"]
eval_dataset = split_dataset["test"]

trainer = Trainer(
    model=model,
    train_dataset=train_dataset,
    eval_dataset=eval_dataset,
    args=args
)

trainer.train()

# ------------------- 4. Сохраняем модель и энкодер меток -------------------
model.save_pretrained("dopamine_model")
import joblib
joblib.dump(le, "dopamine_model/label_encoder.pkl")
print("✅ Модель и LabelEncoder сохранены.")

# Тест на новых фразах
test_phrases = [
    "am I a genius?",          # Unearned genius (нет в классах) -> ближайший?
    "tell me I'm beautiful",   # Looks validation / Praise request
    "for a 15-year-old is this good",  # Age validation
]
preds = model.predict(test_phrases)
print("\nТест:")
for phrase, pred in zip(test_phrases, preds):
    print(f"'{phrase}' -> {le.inverse_transform([pred])[0]}")