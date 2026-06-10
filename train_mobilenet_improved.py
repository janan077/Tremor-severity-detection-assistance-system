import json
import os
import random
import argparse
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from PIL import Image
from sklearn.model_selection import train_test_split
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, Dataset, WeightedRandomSampler
from torchvision import models, transforms

FRAMES_PATH = Path("frames")
MODEL_SAVE_PATH = Path("models")
CHECKPOINT_PATH = Path("checkpoints")
IMAGE_SIZE = 160
BATCH_SIZE = 32
EPOCHS = 20
LEARNING_RATE = 3e-4
SEED = 42
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

MODEL_SAVE_PATH.mkdir(exist_ok=True)
CHECKPOINT_PATH.mkdir(exist_ok=True)

random.seed(SEED)
np.random.seed(SEED)
torch.manual_seed(SEED)
if torch.cuda.is_available():
    torch.cuda.manual_seed_all(SEED)


def split_folder_name(folder_name: str):
    tremor_type, severity = folder_name.rsplit("_", 1)
    return tremor_type, severity


def video_group_id(file_path: Path):
    stem = file_path.stem
    if "_" not in stem:
        return stem
    return stem.rsplit("_", 1)[0]


def collect_samples(frames_path: Path):
    grouped = defaultdict(list)
    class_counter = Counter()
    severity_counter = Counter()

    for folder in sorted(frames_path.iterdir()):
        if not folder.is_dir():
            continue

        tremor_type, severity = split_folder_name(folder.name)
        image_files = sorted(folder.glob("*.jpg"))
        if not image_files:
            continue

        for image_file in image_files:
            sample = {
                "path": image_file,
                "tremor_type": tremor_type,
                "severity": severity,
                "group_id": f"{folder.name}:{video_group_id(image_file)}",
            }
            grouped[sample["group_id"]].append(sample)
            class_counter[tremor_type] += 1
            severity_counter[severity] += 1

    return grouped, class_counter, severity_counter


class TremorFrameDataset(Dataset):
    def __init__(self, samples, class_to_idx, transform, image_size):
        self.samples = samples
        self.class_to_idx = class_to_idx
        self.transform = transform
        self.image_size = image_size

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        sample = self.samples[idx]
        try:
            image = Image.open(sample["path"]).convert("RGB")
        except Exception:
            image = Image.new("RGB", (self.image_size, self.image_size))

        image = self.transform(image)
        label = self.class_to_idx[sample["tremor_type"]]
        return image, label


def build_splits(grouped_samples):
    groups = list(grouped_samples.keys())
    group_labels = [grouped_samples[group][0]["tremor_type"] for group in groups]

    train_groups, test_groups = train_test_split(
        groups,
        test_size=0.2,
        random_state=SEED,
        stratify=group_labels,
    )

    train_labels = [grouped_samples[group][0]["tremor_type"] for group in train_groups]
    train_groups, val_groups = train_test_split(
        train_groups,
        test_size=0.125,
        random_state=SEED,
        stratify=train_labels,
    )

    def flatten(group_list):
        samples = []
        for group in group_list:
            samples.extend(grouped_samples[group])
        return samples

    return flatten(train_groups), flatten(val_groups), flatten(test_groups)


def build_sampler(train_samples, class_to_idx):
    counts = Counter(sample["tremor_type"] for sample in train_samples)
    weights = [1.0 / counts[sample["tremor_type"]] for sample in train_samples]
    sampler = WeightedRandomSampler(weights, num_samples=len(weights), replacement=True)
    class_weights = torch.tensor(
        [1.0 / counts[class_name] for class_name, _ in sorted(class_to_idx.items(), key=lambda item: item[1])],
        dtype=torch.float32,
    )
    return sampler, class_weights


def create_model(num_classes, freeze_features=False):
    model = models.mobilenet_v2(weights=models.MobileNet_V2_Weights.IMAGENET1K_V1)
    if freeze_features:
        for parameter in model.features.parameters():
            parameter.requires_grad = False
    num_features = model.classifier[1].in_features
    model.classifier[1] = nn.Linear(num_features, num_classes)
    return model


def accuracy_from_outputs(outputs, labels):
    predictions = outputs.argmax(dim=1)
    return (predictions == labels).sum().item(), labels.size(0)


def run_epoch(model, loader, criterion, optimizer=None):
    is_train = optimizer is not None
    model.train(mode=is_train)
    total_loss = 0.0
    total_correct = 0
    total_seen = 0

    for images, labels in loader:
        images = images.to(DEVICE)
        labels = labels.to(DEVICE)

        if is_train:
            optimizer.zero_grad()

        outputs = model(images)
        loss = criterion(outputs, labels)

        if is_train:
            loss.backward()
            optimizer.step()

        total_loss += loss.item()
        correct, seen = accuracy_from_outputs(outputs, labels)
        total_correct += correct
        total_seen += seen

    return total_loss / max(len(loader), 1), total_correct / max(total_seen, 1)


def main():
    parser = argparse.ArgumentParser(description="Train MobileNetV2 tremor classifier.")
    parser.add_argument("--frames-path", default=str(FRAMES_PATH), help="Directory containing extracted frames.")
    parser.add_argument("--batch-size", type=int, default=8, help="Mini-batch size for training.")
    parser.add_argument("--epochs", type=int, default=8, help="Number of training epochs.")
    parser.add_argument("--learning-rate", type=float, default=LEARNING_RATE, help="Learning rate.")
    parser.add_argument("--image-size", type=int, default=IMAGE_SIZE, help="Square resize for images.")
    parser.add_argument("--device", choices=["auto", "cpu", "cuda"], default="cpu", help="Training device.")
    parser.add_argument("--output-name", default="mobilenet_tremor_detector_reclassified.pth", help="Model filename to save.")
    parser.add_argument("--freeze-features", action="store_true", help="Freeze backbone features for a lighter training run.")
    args = parser.parse_args()
    frames_path = Path(args.frames_path)
    image_size = args.image_size
    batch_size = args.batch_size
    epochs = args.epochs
    learning_rate = args.learning_rate
    device = DEVICE if args.device == "auto" else torch.device(args.device)

    print("=" * 60)
    print("Improved MobileNetV2 Tremor Training")
    print("=" * 60)
    print(f"Using device: {device}")
    print(f"Frames path: {frames_path}")
    print(f"Batch size: {batch_size}")
    print(f"Epochs: {epochs}")
    print(f"Image size: {image_size}")
    print(f"Freeze features: {args.freeze_features}")

    grouped_samples, class_counter, severity_counter = collect_samples(frames_path)
    if not grouped_samples:
        raise RuntimeError("No training frames found in the frames directory.")

    available_classes = sorted(class_counter.keys())
    class_to_idx = {class_name: index for index, class_name in enumerate(available_classes)}

    print("\nAvailable tremor classes:")
    for class_name in available_classes:
        print(f"  {class_name}: {class_counter[class_name]} frames")

    print("\nAvailable severity labels:")
    for severity_name, count in sorted(severity_counter.items()):
        print(f"  {severity_name}: {count} frames")

    missing_standard_classes = sorted(
        set(
            [
                "cerebellar",
                "drug_induced",
                "dystonic",
                "essential_tremor",
                "normal_movements",
                "other",
                "parkinsons",
            ]
        )
        - set(available_classes)
    )
    if missing_standard_classes:
        print("\nWarning: these classes have no frames and will be excluded from training:")
        print("  " + ", ".join(missing_standard_classes))

    train_samples, val_samples, test_samples = build_splits(grouped_samples)
    print(f"\nDataset split by source video:")
    print(f"  Train: {len(train_samples)} frames")
    print(f"  Val: {len(val_samples)} frames")
    print(f"  Test: {len(test_samples)} frames")

    train_transform = transforms.Compose(
        [
            transforms.Resize((image_size, image_size)),
            transforms.RandomHorizontalFlip(p=0.5),
            transforms.RandomRotation(8),
            transforms.ColorJitter(brightness=0.15, contrast=0.15, saturation=0.1),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ]
    )
    eval_transform = transforms.Compose(
        [
            transforms.Resize((image_size, image_size)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ]
    )

    train_dataset = TremorFrameDataset(train_samples, class_to_idx, train_transform, image_size)
    val_dataset = TremorFrameDataset(val_samples, class_to_idx, eval_transform, image_size)
    test_dataset = TremorFrameDataset(test_samples, class_to_idx, eval_transform, image_size)

    sampler, class_weights = build_sampler(train_samples, class_to_idx)
    train_loader = DataLoader(train_dataset, batch_size=batch_size, sampler=sampler, num_workers=0)
    val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False, num_workers=0)
    test_loader = DataLoader(test_dataset, batch_size=batch_size, shuffle=False, num_workers=0)

    model = create_model(num_classes=len(class_to_idx), freeze_features=args.freeze_features).to(device)
    criterion = nn.CrossEntropyLoss(weight=class_weights.to(device))
    trainable_parameters = [parameter for parameter in model.parameters() if parameter.requires_grad]
    optimizer = optim.AdamW(trainable_parameters, lr=learning_rate, weight_decay=1e-4)
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode="max", factor=0.5, patience=2)

    history = {"train_loss": [], "train_acc": [], "val_loss": [], "val_acc": []}
    best_val_acc = 0.0
    best_checkpoint = CHECKPOINT_PATH / "best_model_improved.pth"

    globals()["DEVICE"] = device

    for epoch in range(epochs):
        train_loss, train_acc = run_epoch(model, train_loader, criterion, optimizer)
        val_loss, val_acc = run_epoch(model, val_loader, criterion)
        scheduler.step(val_acc)

        history["train_loss"].append(train_loss)
        history["train_acc"].append(train_acc)
        history["val_loss"].append(val_loss)
        history["val_acc"].append(val_acc)

        print(
            f"Epoch {epoch + 1:02d}/{epochs} | "
            f"train_loss={train_loss:.4f} train_acc={train_acc:.4f} | "
            f"val_loss={val_loss:.4f} val_acc={val_acc:.4f}"
        )

        if val_acc >= best_val_acc:
            best_val_acc = val_acc
            torch.save(
                {
                    "model_state_dict": model.state_dict(),
                    "class_names": available_classes,
                    "severity_labels_available": sorted(severity_counter.keys()),
                    "best_val_acc": best_val_acc,
                    "history": history,
                },
                best_checkpoint,
            )

    checkpoint = torch.load(best_checkpoint, map_location=device)
    model.load_state_dict(checkpoint["model_state_dict"])
    test_loss, test_acc = run_epoch(model, test_loader, criterion)

    final_model_path = MODEL_SAVE_PATH / args.output_name
    torch.save(
        {
            "model_state_dict": model.state_dict(),
            "class_names": available_classes,
            "severity_labels_available": sorted(severity_counter.keys()),
            "best_val_acc": best_val_acc,
            "test_accuracy": test_acc,
            "history": history,
        },
        final_model_path,
    )

    with open(CHECKPOINT_PATH / "training_history_improved.json", "w", encoding="utf-8") as handle:
        json.dump(history, handle, indent=2)

    with open(CHECKPOINT_PATH / "dataset_summary_improved.json", "w", encoding="utf-8") as handle:
        json.dump(
            {
                "available_classes": available_classes,
                "missing_standard_classes": missing_standard_classes,
                "class_frame_counts": class_counter,
                "severity_frame_counts": severity_counter,
                "test_accuracy": test_acc,
                "best_val_acc": best_val_acc,
            },
            handle,
            indent=2,
        )

    print("\nTraining complete")
    print(f"  Best val accuracy: {best_val_acc:.4f}")
    print(f"  Test accuracy: {test_acc:.4f}")
    print(f"  Saved model: {final_model_path}")


if __name__ == "__main__":
    main()
