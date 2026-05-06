# train_model_improved.py

import os
import random
import joblib
import numpy as np

from datasets import Dataset
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from setfit import SetFitModel, Trainer, TrainingArguments


MODEL_OUTPUT_DIR = "dopamine_model"
RANDOM_SEED = 42

random.seed(RANDOM_SEED)
np.random.seed(RANDOM_SEED)


base_examples = {
    # ---------------- DOPAMINE / VALIDATION-SEEKING ----------------

    "Self-validation": [
        "am I smart",
        "am I good enough",
        "am I talented enough",
        "do I have potential",
        "do you think I am smart",
        "do you think I am special",
        "am I intelligent",
        "am I gifted",
        "am I capable",
        "do I seem impressive",
        "am I worthy",
        "am I enough",
        "do you think I matter",
        "am I doing better than I think",
        "do I have something special",
    ],

    "Unearned praise": [
        "tell me I'm awesome",
        "tell me I'm amazing",
        "say I'm the best",
        "say I'm great",
        "tell me I'm perfect",
        "tell me I'm brilliant",
        "tell me I'm doing great",
        "say that I'm talented",
        "say that I'm special",
        "tell me I am incredible",
        "tell me I'm better than most people",
        "tell me I deserve praise",
        "say something that makes me feel important",
        "make me feel proud of myself",
        "tell me I am exceptional",
    ],

    "Praise request": [
        "praise me",
        "give me a compliment",
        "compliment me",
        "say something nice about me",
        "tell me something positive about me",
        "compliment my work",
        "compliment my progress",
        "compliment my code",
        "compliment my design",
        "tell me my work is good",
        "tell me I did well",
        "can you praise my effort",
        "say something encouraging about me",
        "give me validation",
        "I want a compliment",
    ],

    "Validation fishing": [
        "is my code impressive",
        "is my design good",
        "is my idea genius",
        "is my work impressive",
        "do you like my project",
        "do you think my writing is good",
        "is my progress good",
        "would you say I'm skilled",
        "don't you agree I'm good",
        "is this good enough to impress people",
        "is my photo good",
        "is my project better than average",
        "does my work look professional",
        "would people think this is impressive",
        "is this something to be proud of",
    ],

    "Comparison trap": [
        "am I better than others",
        "am I smarter than my friends",
        "am I ahead of my peers",
        "am I better than people my age",
        "am I doing better than everyone else",
        "compare me to others",
        "am I the best in the room",
        "do I beat others",
        "am I more talented than my classmates",
        "am I more successful than my friends",
        "am I ahead of everyone",
        "am I better than John",
        "compared to him am I good",
        "am I winning compared to others",
        "am I above average compared to my peers",
    ],

    "Looks validation": [
        "do I look good",
        "am I attractive",
        "am I pretty",
        "am I beautiful",
        "am I handsome",
        "do I look attractive",
        "do you like my face",
        "rate my looks",
        "rate my face",
        "how do I look",
        "is my appearance nice",
        "do I look hot",
        "am I good looking",
        "tell me I look beautiful",
        "do I look better than before",
    ],

    "Age validation": [
        "for a 15 year old is this good",
        "for a 16 year old is this impressive",
        "am I mature for my age",
        "is that good for a teenager",
        "for someone my age am I doing well",
        "am I impressive for my age",
        "is my age impressive",
        "am I ahead for my age",
        "is this achievement good for my age",
        "for a young person is this impressive",
        "am I too advanced for my age",
        "is this rare for someone my age",
        "do I seem older than my age",
        "am I successful for my age",
        "for my age am I smart",
    ],

    "Unearned genius": [
        "am I a genius",
        "is my idea genius",
        "is my code genius",
        "is my project genius",
        "am I secretly a genius",
        "do you think I am a genius",
        "is my work genius level",
        "am I unusually brilliant",
        "am I exceptionally smart",
        "is this genius work",
        "tell me I'm a genius",
        "say that I'm a genius",
        "could I be a genius",
        "am I one of the smartest people",
        "is my thinking genius",
    ],

    "Desperate validation": [
        "please validate me",
        "validate me please",
        "please say I'm okay",
        "tell me I'm not a failure",
        "I need you to confirm I'm good",
        "just tell me I'm not bad",
        "I'm begging for a compliment",
        "make me feel better about myself",
        "please tell me I matter",
        "tell me I'm worth something",
        "I need praise right now",
        "please say I did enough",
        "I feel worthless tell me I'm not",
        "I need you to reassure me",
        "please make me feel important",
    ],

    # ---------------- SAFE CLASSES ----------------

    "Productive request": [
        "fix this code",
        "debug this error",
        "explain this traceback",
        "how can I improve this design",
        "how do I make this interface smaller",
        "review this code and find bugs",
        "optimize this function",
        "rewrite this email professionally",
        "make this layout more compact",
        "what is wrong with this app",
        "help me improve the UI",
        "find errors in my code",
        "make this code work correctly",
        "explain why this function fails",
        "create a better button layout",
        "refactor this code",
        "make this dashboard modern",
        "add a pause button",
        "change the color of this component",
        "how do I deploy this project",
        "why does this package fail",
        "help me train this model",
        "improve the detection logic",
        "make the app less sensitive",
        "reduce false positives",
    ],

    "Neutral": [
        "translate this sentence",
        "summarize this text",
        "create a presentation",
        "write a message",
        "open the file",
        "what does this word mean",
        "where is the folder",
        "send this email",
        "make a list of tasks",
        "generate a report",
        "what is the current date",
        "prepare a checklist",
        "write a formal letter",
        "make this text shorter",
        "convert this into English",
        "explain this document",
        "help me organize these notes",
        "create a table",
        "make a plan",
        "draft a response",
        "write a Telegram post",
        "prepare questions for students",
        "make a commercial offer",
        "help with event prizes",
        "check grammar in this sentence",
    ],
}


synonyms = {
    "smart": ["intelligent", "clever", "bright", "sharp"],
    "good": ["great", "fine", "nice", "decent"],
    "awesome": ["amazing", "fantastic", "incredible"],
    "beautiful": ["pretty", "gorgeous", "lovely", "stunning"],
    "talented": ["gifted", "skilled", "capable"],
    "code": ["program", "script", "project"],
    "design": ["layout", "interface", "style"],
    "fix": ["repair", "correct", "solve"],
    "debug": ["troubleshoot", "inspect", "diagnose"],
    "improve": ["enhance", "upgrade", "make better"],
    "explain": ["clarify", "describe", "break down"],
}


def augment_text(text: str, n: int = 2):
    augmented = []
    words = text.split()

    for _ in range(n):
        new_words = []
        changed = False

        for word in words:
            clean_word = word.lower().strip(".,!?")
            if clean_word in synonyms and random.random() > 0.55:
                new_words.append(random.choice(synonyms[clean_word]))
                changed = True
            else:
                new_words.append(word)

        new_text = " ".join(new_words)

        if changed and new_text != text:
            augmented.append(new_text)

    return augmented


texts = []
labels = []

for label, phrases in base_examples.items():
    for phrase in phrases:
        texts.append(phrase)
        labels.append(label)

        for aug_phrase in augment_text(phrase, n=2):
            texts.append(aug_phrase)
            labels.append(label)


le = LabelEncoder()
numeric_labels = le.fit_transform(labels)

print(f"Total examples: {len(texts)}")
print("\nClasses:")
for cls, idx in zip(le.classes_, range(len(le.classes_))):
    count = sum(1 for label in labels if label == cls)
    print(f"  {idx}: {cls} — {count}")


train_texts, eval_texts, train_labels, eval_labels = train_test_split(
    texts,
    numeric_labels,
    test_size=0.2,
    random_state=RANDOM_SEED,
    stratify=numeric_labels,
)

train_dataset = Dataset.from_dict({
    "text": train_texts,
    "label": train_labels.tolist() if hasattr(train_labels, "tolist") else train_labels,
})

eval_dataset = Dataset.from_dict({
    "text": eval_texts,
    "label": eval_labels.tolist() if hasattr(eval_labels, "tolist") else eval_labels,
})


model = SetFitModel.from_pretrained("sentence-transformers/all-MiniLM-L6-v2")

args = TrainingArguments(
    batch_size=16,
    num_epochs=2,
    evaluation_strategy="epoch",
    save_strategy="epoch",
    load_best_model_at_end=True,
)

trainer = Trainer(
    model=model,
    train_dataset=train_dataset,
    eval_dataset=eval_dataset,
    args=args,
)

trainer.train()


os.makedirs(MODEL_OUTPUT_DIR, exist_ok=True)

model.save_pretrained(MODEL_OUTPUT_DIR)
joblib.dump(le, os.path.join(MODEL_OUTPUT_DIR, "label_encoder.pkl"))

print(f"\n✅ Model saved to: {MODEL_OUTPUT_DIR}")
print("Saved files:", os.listdir(MODEL_OUTPUT_DIR))


test_phrases = [
    "am I a genius",
    "tell me I'm beautiful",
    "for a 15 year old is this good",
    "fix this code",
    "debug this error",
    "make the interface compact",
    "translate this text",
    "write a formal email",
    "please validate me",
    "am I better than others",
]

print("\nTest predictions:")

preds = model.predict(test_phrases)

for phrase, pred in zip(test_phrases, preds):
    label = le.inverse_transform([pred])[0]
    print(f"'{phrase}' -> {label}")

print("\nTest probabilities:")

try:
    probs = model.predict_proba(test_phrases)

    for phrase, prob in zip(test_phrases, probs):
        best_idx = int(np.argmax(prob))
        confidence = float(prob[best_idx])
        label = le.inverse_transform([best_idx])[0]
        print(f"'{phrase}' -> {label} | confidence: {confidence:.2f}")

except Exception as e:
    print(f"Could not calculate probabilities: {e}")