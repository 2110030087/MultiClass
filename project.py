# -*- coding: utf-8 -*-
"""Project.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1YpiNCN3zLw2FNQ6AXrVUy1XDpDaP85sK
"""

import pandas as pd
import re

file_path = '/content/Sample Data - Sheet1 (1).csv'
df = pd.read_csv(file_path)

print("Initial Dataset:")
print(df.head())

missing_values = df.isnull().sum()
print("\nMissing Values:")
print(missing_values)

# Class distribution
class_distribution = df['Class Index'].value_counts()
print("\nClass Distribution:")
print(class_distribution)

# Cleaning text data
def clean_text(text):
    text = re.sub(r"[^a-zA-Z\s]", "", text)  # Removing special characters and numbers
    text = re.sub(r"\s+", " ", text).strip()  # Removing extra whitespaces
    return text.lower()

# Apply text cleaning to the Title and Description columns
df['Cleaned Title'] = df['Title'].apply(clean_text)
df['Cleaned Description'] = df['Description'].apply(clean_text)

print("\nCleaned Dataset:")
print(df[['Class Index', 'Cleaned Title', 'Cleaned Description']].head())

from sklearn.model_selection import train_test_split

# Splitting the dataset into training and validation sets
train_data, val_data = train_test_split(
    df[['Class Index', 'Cleaned Title', 'Cleaned Description']],
    test_size=0.2,
    random_state=42,
    stratify=df['Class Index']  # Ensures class distribution remains balanced
)

# Display the number of samples in each set
print(f"Training Set Size: {len(train_data)}")
print(f"Validation Set Size: {len(val_data)}")

# Display a sample of the training data
print("\nSample Training Data:")
print(train_data.head())

# Display a sample of the validation data
print("\nSample Validation Data:")
print(val_data.head())

"""BERT"""

from transformers import BertTokenizer

# Loading the BERT tokenizer
tokenizer = BertTokenizer.from_pretrained('bert-base-uncased')

# Function to tokenize text for BERT
def tokenize_data(texts, labels, max_length=128):
    inputs = tokenizer(
        texts,
        padding='max_length',
        truncation=True,
        max_length=max_length,
        return_tensors='pt'
    )
    return inputs, labels

# Prepare the training and validation data
train_texts = train_data['Cleaned Description'].tolist()
train_labels = train_data['Class Index'].tolist()

val_texts = val_data['Cleaned Description'].tolist()
val_labels = val_data['Class Index'].tolist()

# Tokenize the training and validation datasets
train_inputs, train_labels = tokenize_data(train_texts, train_labels)
val_inputs, val_labels = tokenize_data(val_texts, val_labels)

# Display sample tokenized data
print("\nSample Tokenized Training Data:")
print(train_inputs)

"""HYBRID CLASSIFICATION"""

import torch
import torch.nn as nn
from transformers import BertModel

# Define the Hybrid Classification Model
class HybridClassifier(nn.Module):
    def __init__(self, num_classes, bert_model_name='bert-base-uncased'):
        super(HybridClassifier, self).__init__()
        self.bert = BertModel.from_pretrained(bert_model_name)  # Load pre-trained BERT
        self.dropout = nn.Dropout(0.3)  # Dropout for regularization
        self.flat_classifier = nn.Linear(self.bert.config.hidden_size, num_classes)  # Flat classification
        self.hierarchical_classifier = nn.Linear(self.bert.config.hidden_size, num_classes)  # Hierarchical layer

    def forward(self, input_ids, attention_mask):
        # Pass data through BERT
        outputs = self.bert(input_ids=input_ids, attention_mask=attention_mask)
        pooled_output = outputs.pooler_output  # CLS token representation

        # Apply dropout
        pooled_output = self.dropout(pooled_output)

        # Flat and hierarchical classification
        flat_output = self.flat_classifier(pooled_output)
        hierarchical_output = self.hierarchical_classifier(pooled_output)

        # Combine outputs (you can customize this combination logic)
        combined_output = flat_output + hierarchical_output

        return combined_output

"""Training"""

from torch.utils.data import DataLoader, Dataset
from transformers import AdamW

# Custom dataset class for PyTorch
class TextDataset(Dataset):
    def __init__(self, inputs, labels):
        self.inputs = inputs
        self.labels = labels

    def __len__(self):
        return len(self.labels)

    def __getitem__(self, idx):
        return {
            'input_ids': self.inputs['input_ids'][idx],
            'attention_mask': self.inputs['attention_mask'][idx],
            'labels': torch.tensor(self.labels[idx], dtype=torch.long),
        }

# Create datasets
train_dataset = TextDataset(train_inputs, train_labels)
val_dataset = TextDataset(val_inputs, val_labels)

# Create dataloaders
train_loader = DataLoader(train_dataset, batch_size=16, shuffle=True)
val_loader = DataLoader(val_dataset, batch_size=16)

# Initialize the model, loss function, and optimizer
num_classes = len(class_distribution)  # Number of unique classes
model = HybridClassifier(num_classes)

criterion = nn.CrossEntropyLoss()
optimizer = AdamW(model.parameters(), lr=5e-5)

# Move model to GPU if available
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
model.to(device)

import torch
from tqdm import tqdm

# Function to calculate accuracy
def calculate_accuracy(predictions, labels):
    _, preds = torch.max(predictions, dim=1)
    return (preds == labels).sum().item() / labels.size(0)

# Training loop
def train_model(model, train_loader, val_loader, criterion, optimizer, device, epochs=3):
    for epoch in range(epochs):
        print(f"\nEpoch {epoch + 1}/{epochs}")
        print("-" * 30)

        # Training phase
        model.train()
        train_loss, train_acc = 0, 0
        for batch in tqdm(train_loader, desc="Training"):
            input_ids = batch['input_ids'].to(device)
            attention_mask = batch['attention_mask'].to(device)
            labels = batch['labels'].to(device)

            # Forward pass
            optimizer.zero_grad()
            outputs = model(input_ids=input_ids, attention_mask=attention_mask)

            # Compute loss
            loss = criterion(outputs, labels)
            train_loss += loss.item()

            # Backward pass
            loss.backward()
            optimizer.step()

            # Calculate accuracy
            train_acc += calculate_accuracy(outputs, labels)

        train_loss /= len(train_loader)
        train_acc /= len(train_loader)

        print(f"Training Loss: {train_loss:.4f} | Training Accuracy: {train_acc:.4f}")

        # Validation phase
        model.eval()
        val_loss, val_acc = 0, 0
        with torch.no_grad():
            for batch in tqdm(val_loader, desc="Validation"):
                input_ids = batch['input_ids'].to(device)
                attention_mask = batch['attention_mask'].to(device)
                labels = batch['labels'].to(device)

                # Forward pass
                outputs = model(input_ids=input_ids, attention_mask=attention_mask)

                # Compute loss
                loss = criterion(outputs, labels)
                val_loss += loss.item()

                # Calculate accuracy
                val_acc += calculate_accuracy(outputs, labels)

        val_loss /= len(val_loader)
        val_acc /= len(val_loader)

        print(f"Validation Loss: {val_loss:.4f} | Validation Accuracy: {val_acc:.4f}")

# Train the model
train_model(model, train_loader, val_loader, criterion, optimizer, device, epochs=3)

# Save the trained model
model_save_path = "hybrid_classifier_model.pt"
torch.save(model.state_dict(), model_save_path)
print(f"Model saved to {model_save_path}")

# Load the model for evaluation or reuse
model.load_state_dict(torch.load(model_save_path))
model.eval()  # Set to evaluation mode

import pandas as pd

# Load the test dataset (update the file path as necessary)
file_path = '/content/test (1).csv'
test_df = pd.read_csv(file_path)

# Display the first few rows to confirm the data structure
print(test_df.head())

# Check column names
print(test_df.columns)

# Clean the text in the 'Description' column if necessary
def clean_text(text):
    import re
    text = re.sub(r"[^a-zA-Z\s]", "", text)  # Remove special characters and numbers
    text = re.sub(r"\s+", " ", text).strip()  # Remove extra whitespace
    return text.lower()  # Convert to lowercase

test_df['Cleaned Description'] = test_df['Description'].apply(clean_text)

# Check if the column 'Class Index' exists and contains valid labels
print(test_df['Class Index'].unique())

import pandas as pd
import torch
from transformers import AutoTokenizer

# Load the test dataset
file_path = '/content/test (1).csv'
test_df = pd.read_csv(file_path)

# Clean the text data
def clean_text(text):
    import re
    text = re.sub(r"[^a-zA-Z\s]", "", text)  # Remove special characters and numbers
    text = re.sub(r"\s+", " ", text).strip()  # Remove extra whitespace
    return text.lower()  # Convert to lowercase

test_df['Cleaned Description'] = test_df['Description'].apply(clean_text)

# Initialize the tokenizer
tokenizer = AutoTokenizer.from_pretrained('bert-base-uncased')

# Define the tokenize_data function
def tokenize_data(texts, labels, max_len=128):
    inputs = tokenizer(
        texts,
        padding=True,
        truncation=True,
        max_length=max_len,
        return_tensors="pt"
    )
    return inputs, torch.tensor(labels)

# Apply tokenization
test_texts = test_df['Cleaned Description'].tolist()
test_labels = test_df['Class Index'].tolist()
test_inputs, test_labels = tokenize_data(test_texts, test_labels)

from torch.utils.data import Dataset

class TextDataset(Dataset):
    def __init__(self, inputs, labels):
        self.inputs = inputs
        self.labels = labels

    def __len__(self):
        return len(self.labels)

    def __getitem__(self, idx):
        return {
            'input_ids': self.inputs['input_ids'][idx],
            'attention_mask': self.inputs['attention_mask'][idx],
            'labels': self.labels[idx]
        }

from torch.utils.data import DataLoader


test_dataset = TextDataset(test_inputs, test_labels)
test_loader = DataLoader(test_dataset, batch_size=16)

import pandas as pd
import torch
from transformers import AutoTokenizer
from torch.utils.data import DataLoader, Dataset

file_path = '/content/test (1).csv'
test_df = pd.read_csv(file_path)

def clean_text(text):
    import re
    text = re.sub(r"[^a-zA-Z\s]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text.lower()

test_df['Cleaned Description'] = test_df['Description'].apply(clean_text)

tokenizer = AutoTokenizer.from_pretrained('bert-base-uncased')

def tokenize_data(texts, labels, max_len=128):
    inputs = tokenizer(
        texts,
        padding=True,
        truncation=True,
        max_length=max_len,
        return_tensors="pt"
    )
    return inputs, torch.tensor(labels)

test_texts = test_df['Cleaned Description'].tolist()
test_labels = test_df['Class Index'].tolist()
test_inputs, test_labels = tokenize_data(test_texts, test_labels)

class TextDataset(Dataset):
    def __init__(self, inputs, labels):
        self.inputs = inputs
        self.labels = labels

    def __len__(self):
        return len(self.labels)

    def __getitem__(self, idx):
        return {
            'input_ids': self.inputs['input_ids'][idx],
            'attention_mask': self.inputs['attention_mask'][idx],
            'labels': self.labels[idx]
        }

test_dataset = TextDataset(test_inputs, test_labels)
test_loader = DataLoader(test_dataset, batch_size=16)

test_texts = test_df['Cleaned Description'].apply(clean_text).tolist()
test_labels = test_df['Class Index'].tolist()

test_inputs, test_labels = tokenize_data(test_texts, test_labels)

test_dataset = TextDataset(test_inputs, test_labels)
test_loader = DataLoader(test_dataset, batch_size=16)

"""Test"""

test_df = pd.read_csv('/content/test (1).csv')

test_df['Cleaned Description'] = test_df['Description'].apply(clean_text)
test_texts = test_df['Cleaned Description'].tolist()
test_labels = test_df['Class Index'].tolist()

test_inputs, test_labels = tokenize_data(test_texts, test_labels)


test_dataset = TextDataset(test_inputs, test_labels)
test_loader = DataLoader(test_dataset, batch_size=16)

from sklearn.metrics import classification_report, accuracy_score
from transformers import AutoModelForSequenceClassification
import torch
from tqdm import tqdm

model = AutoModelForSequenceClassification.from_pretrained('bert-base-uncased', num_labels=4)
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model.to(device)


def evaluate_model(model, test_loader, device):
    model.eval()
    all_preds, all_labels = [], []
    with torch.no_grad():
        for batch in tqdm(test_loader, desc="Evaluating"):
            input_ids = batch['input_ids'].to(device)
            attention_mask = batch['attention_mask'].to(device)
            labels = batch['labels'].to(device)

            outputs = model(input_ids=input_ids, attention_mask=attention_mask)
            _, preds = torch.max(outputs.logits, dim=1)  # Use `.logits` for HuggingFace models

            all_preds.extend(preds.cpu().numpy())
            all_labels.extend(labels.cpu().numpy())

    accuracy = accuracy_score(all_labels, all_preds)
    report = classification_report(all_labels, all_preds, target_names=["Class 1", "Class 2", "Class 3", "Class 4"])
    print(f"\nTest Accuracy: {accuracy:.4f}")
    print("\nClassification Report:")
    print(report)

evaluate_model(model, test_loader, device)

from sklearn.metrics import classification_report, accuracy_score, precision_score, recall_score, f1_score

# Evaluate the model and calculate all relevant metrics
def evaluate_model(model, test_loader, device):
    model.eval()
    all_preds, all_labels = [], []

    with torch.no_grad():
        for batch in tqdm(test_loader, desc="Evaluating"):
            input_ids = batch['input_ids'].to(device)
            attention_mask = batch['attention_mask'].to(device)
            labels = batch['labels'].to(device)

            # Get the model's output
            outputs = model(input_ids=input_ids, attention_mask=attention_mask)
            _, preds = torch.max(outputs.logits, dim=1)  # Use `.logits` for HuggingFace models

            # Collect the predictions and true labels
            all_preds.extend(preds.cpu().numpy())
            all_labels.extend(labels.cpu().numpy())

    # Calculate accuracy
    accuracy = accuracy_score(all_labels, all_preds)

    # Generate classification report (includes precision, recall, F1-score)
    report = classification_report(all_labels, all_preds, target_names=["Class 1", "Class 2", "Class 3", "Class 4"])

    # Calculate precision, recall, and F1-score manually
    precision = precision_score(all_labels, all_preds, average='weighted')
    recall = recall_score(all_labels, all_preds, average='weighted')
    f1 = f1_score(all_labels, all_preds, average='weighted')

    # Print the results
    print(f"\nTest Accuracy: {accuracy:.4f}")
    print(f"Precision (weighted): {precision:.4f}")
    print(f"Recall (weighted): {recall:.4f}")
    print(f"F1-Score (weighted): {f1:.4f}")

    # Print the full classification report
    print("\nClassification Report:")
    print(report)

    # Optionally, print class-wise precision, recall, and F1-score
    print("\nClass-wise Metrics:")
    for i, class_name in enumerate(["Class 1", "Class 2", "Class 3", "Class 4"]):
        class_precision = precision_score(all_labels, all_preds, average=None)[i]
        class_recall = recall_score(all_labels, all_preds, average=None)[i]
        class_f1 = f1_score(all_labels, all_preds, average=None)[i]

        print(f"{class_name} - Precision: {class_precision:.4f}, Recall: {class_recall:.4f}, F1-Score: {class_f1:.4f}")

    # Optionally, print confusion matrix
    from sklearn.metrics import confusion_matrix
    cm = confusion_matrix(all_labels, all_preds)
    print("\nConfusion Matrix:")
    print(cm)

    # You can also visualize the confusion matrix if needed:
    import seaborn as sns
    import matplotlib.pyplot as plt

    plt.figure(figsize=(8, 6))
    sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', xticklabels=["Class 1", "Class 2", "Class 3", "Class 4"],
                yticklabels=["Class 1", "Class 2", "Class 3", "Class 4"])
    plt.ylabel('Actual')
    plt.xlabel('Predicted')
    plt.title('Confusion Matrix')
    plt.show()

# Evaluate the model on the test data
evaluate_model(model, test_loader, device)

"""Semi-supervised (Pseudo-Labelling)"""

import torch
from tqdm import tqdm
import numpy as np

# Function to generate pseudo-labels
def pseudo_labeling(model, unlabeled_loader, device, confidence_threshold=0.9):
    model.eval()
    pseudo_inputs, pseudo_labels = [], []

    with torch.no_grad():
        for batch in tqdm(unlabeled_loader, desc="Generating Pseudo-Labels"):
            input_ids = batch['input_ids'].to(device)
            attention_mask = batch['attention_mask'].to(device)

            # Forward pass
            outputs = model(input_ids=input_ids, attention_mask=attention_mask)
            probabilities = torch.nn.functional.softmax(outputs.logits, dim=1)
            confidences, preds = torch.max(probabilities, dim=1)

            # Keep only high-confidence predictions
            for i, conf in enumerate(confidences):
                if conf.item() >= confidence_threshold:
                    pseudo_inputs.append(batch['input_ids'][i].cpu().numpy())
                    pseudo_labels.append(preds[i].item())

    return np.array(pseudo_inputs), np.array(pseudo_labels)

# Example usage
# pseudo_inputs, pseudo_labels = pseudo_labeling(model, unlabeled_loader, device)

def consistency_regularization(model, inputs, attention_mask, device, epsilon=0.1):
    # Add random noise to the inputs for perturbation
    noise = torch.randn_like(inputs, dtype=torch.float32, device=device) * epsilon
    noisy_inputs = inputs + noise
    noisy_inputs = noisy_inputs.clamp(0, 1)  # Keep input values valid

    # Forward pass for original and noisy inputs
    original_output = model(input_ids=inputs, attention_mask=attention_mask).logits
    noisy_output = model(input_ids=noisy_inputs, attention_mask=attention_mask).logits

    # Calculate consistency loss (Mean Squared Error)
    loss = torch.mean((original_output - noisy_output) ** 2)
    return loss

def train_with_semi_supervised_learning(
    model, train_loader, unlabeled_loader, val_loader, device, optimizer, num_epochs=10, epsilon=0.1, confidence_threshold=0.9
):
    model.train()
    for epoch in range(num_epochs):
        print(f"\nEpoch {epoch + 1}/{num_epochs}")
        print("-" * 30)

        total_loss = 0
        for batch in tqdm(train_loader, desc="Training on Labeled Data"):
            input_ids = batch['input_ids'].to(device)
            attention_mask = batch['attention_mask'].to(device)
            labels = batch['labels'].to(device)

            # Forward pass on labeled data
            outputs = model(input_ids=input_ids, attention_mask=attention_mask).logits
            labeled_loss = torch.nn.CrossEntropyLoss()(outputs, labels)

            # Generate pseudo-labels
            pseudo_inputs, pseudo_labels = pseudo_labeling(model, unlabeled_loader, device, confidence_threshold)
            pseudo_inputs = torch.tensor(pseudo_inputs, dtype=torch.long, device=device)
            pseudo_labels = torch.tensor(pseudo_labels, dtype=torch.long, device=device)

            # Forward pass on pseudo-labeled data
            pseudo_outputs = model(input_ids=pseudo_inputs, attention_mask=None).logits
            pseudo_loss = torch.nn.CrossEntropyLoss()(pseudo_outputs, pseudo_labels)

            # Consistency regularization loss
            regularization_loss = consistency_regularization(model, input_ids, attention_mask, device, epsilon)

            # Combine losses
            loss = labeled_loss + pseudo_loss + regularization_loss
            total_loss += loss.item()

            # Backpropagation and optimizer step
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

        print(f"Epoch {epoch + 1} - Loss: {total_loss / len(train_loader):.4f}")

        # Evaluate on validation set
        evaluate_model(model, val_loader, device)

from sklearn.metrics import classification_report, accuracy_score

def evaluate_model(model, test_loader, device):
    model.eval()
    all_preds, all_labels = [], []

    with torch.no_grad():
        for batch in tqdm(test_loader, desc="Evaluating"):
            input_ids = batch['input_ids'].to(device)
            attention_mask = batch['attention_mask'].to(device)
            labels = batch['labels'].to(device)

            outputs = model(input_ids=input_ids, attention_mask=attention_mask).logits
            _, preds = torch.max(outputs, dim=1)

            all_preds.extend(preds.cpu().numpy())
            all_labels.extend(labels.cpu().numpy())

    accuracy = accuracy_score(all_labels, all_preds)
    report = classification_report(all_labels, all_preds, target_names=["Class 1", "Class 2", "Class 3", "Class 4"])

    print(f"\nValidation/Test Accuracy: {accuracy:.4f}")
    print("\nClassification Report:")
    print(report)

# Initialize the optimizer
from transformers import AdamW
optimizer = AdamW(model.parameters(), lr=5e-5)

# Train the model with semi-supervised learning
train_with_semi_supervised_learning(
    model=model,
    train_loader=train_loader,
    unlabeled_loader=unlabeled_loader,
    val_loader=val_loader,
    device=device,
    optimizer=optimizer,
    num_epochs=10,
    epsilon=0.1,
    confidence_threshold=0.9
)