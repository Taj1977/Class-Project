"""
Diabetes Prediction Project - Pima Indians Diabetes Dataset
Full pipeline: load -> clean -> EDA -> train (LogReg, RandomForest) -> evaluate -> save figures/metrics
"""
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
import json
import os

from sklearn.model_selection import train_test_split, cross_val_score, StratifiedKFold
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score, roc_curve, confusion_matrix, classification_report
)
from sklearn.impute import SimpleImputer

sns.set_theme(style="whitegrid")
PALETTE = ["#2E5C8A", "#D9824B", "#4F8A6D", "#A64B5C"]
sns.set_palette(PALETTE)

BASE = "/home/claude/diabetes_project"
FIG = f"{BASE}/figures"
os.makedirs(FIG, exist_ok=True)

# ---------------------------------------------------------
# 1. LOAD DATA
# ---------------------------------------------------------
cols = ["Pregnancies", "Glucose", "BloodPressure", "SkinThickness", "Insulin",
        "BMI", "DiabetesPedigreeFunction", "Age", "Outcome"]
df = pd.read_csv(f"{BASE}/data/diabetes_raw.csv", names=cols)
df.to_csv(f"{BASE}/data/diabetes.csv", index=False)

print("Shape:", df.shape)
print(df.describe())

results = {}
results["n_rows"] = int(df.shape[0])
results["n_cols"] = int(df.shape[1]) - 1
results["class_counts"] = df["Outcome"].value_counts().to_dict()
results["class_pct"] = (df["Outcome"].value_counts(normalize=True) * 100).round(1).to_dict()

# ---------------------------------------------------------
# 2. DATA CLEANING - biologically implausible zeros treated as missing
# ---------------------------------------------------------
zero_invalid_cols = ["Glucose", "BloodPressure", "SkinThickness", "Insulin", "BMI"]
missing_summary = {}
for c in zero_invalid_cols:
    missing_summary[c] = int((df[c] == 0).sum())
results["missing_as_zero"] = missing_summary

df_clean = df.copy()
for c in zero_invalid_cols:
    df_clean[c] = df_clean[c].replace(0, np.nan)

# NOTE: Imputation is deliberately done AFTER the train/test split (see step 4)
# using only training-set medians, to avoid leaking test-set or label information
# into the cleaning step. A version of this dataset with NaNs marked is used for EDA.
results["summary_stats"] = df_clean.describe().round(2).to_dict()

# Separate dataframe imputed on FULL data, used ONLY for visualization/EDA (not modeling)
df_eda = df_clean.copy()
for c in zero_invalid_cols:
    df_eda[c] = df_eda[c].fillna(df_eda[c].median())

# ---------------------------------------------------------
# 3. EDA FIGURES
# ---------------------------------------------------------

# 3a. Class balance
fig, ax = plt.subplots(figsize=(5, 4))
counts = df["Outcome"].value_counts().sort_index()
bars = ax.bar(["No Diabetes (0)", "Diabetes (1)"], counts.values, color=[PALETTE[0], PALETTE[1]])
for b, v in zip(bars, counts.values):
    ax.text(b.get_x() + b.get_width()/2, v + 8, str(v), ha="center", fontweight="bold")
ax.set_ylabel("Number of Patients")
ax.set_title("Class Distribution: Diabetes Outcome")
plt.tight_layout()
plt.savefig(f"{FIG}/class_balance.png", dpi=150)
plt.close()

# 3b. Correlation heatmap
fig, ax = plt.subplots(figsize=(7, 6))
corr = df_eda.corr()
sns.heatmap(corr, annot=True, fmt=".2f", cmap="vlag", center=0, ax=ax,
            cbar_kws={"shrink": 0.8}, linewidths=0.5)
ax.set_title("Feature Correlation Matrix")
plt.tight_layout()
plt.savefig(f"{FIG}/correlation_heatmap.png", dpi=150)
plt.close()

# 3c. Distribution of key features by outcome
key_feats = ["Glucose", "BMI", "Age", "Insulin"]
fig, axes = plt.subplots(2, 2, figsize=(10, 8))
for ax, feat in zip(axes.flat, key_feats):
    sns.kdeplot(data=df_eda, x=feat, hue="Outcome", fill=True, alpha=0.4,
                palette=[PALETTE[0], PALETTE[1]], ax=ax, common_norm=False)
    ax.set_title(f"{feat} Distribution by Outcome")
plt.tight_layout()
plt.savefig(f"{FIG}/feature_distributions.png", dpi=150)
plt.close()

# 3d. Boxplots for outlier inspection
fig, axes = plt.subplots(2, 4, figsize=(16, 8))
feat_all = ["Pregnancies", "Glucose", "BloodPressure", "SkinThickness",
            "Insulin", "BMI", "DiabetesPedigreeFunction", "Age"]
for ax, feat in zip(axes.flat, feat_all):
    sns.boxplot(data=df_eda, y=feat, x="Outcome", ax=ax, palette=[PALETTE[0], PALETTE[1]])
    ax.set_title(feat, fontsize=10)
    ax.set_xlabel("")
plt.tight_layout()
plt.savefig(f"{FIG}/boxplots.png", dpi=150)
plt.close()

# ---------------------------------------------------------
# 4. TRAIN / TEST SPLIT + IMPUTATION (train-only stats) + SCALING
# ---------------------------------------------------------
X = df_clean.drop(columns=["Outcome"])
y = df_clean["Outcome"]

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)

# Impute missing values using ONLY training-set medians (no leakage from test set or labels)
imputer = SimpleImputer(strategy="median")
X_train = pd.DataFrame(imputer.fit_transform(X_train), columns=X.columns, index=X_train.index)
X_test = pd.DataFrame(imputer.transform(X_test), columns=X.columns, index=X_test.index)

scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train)
X_test_scaled = scaler.transform(X_test)

results["train_size"] = int(X_train.shape[0])
results["test_size"] = int(X_test.shape[0])

# ---------------------------------------------------------
# 5. MODEL 1: LOGISTIC REGRESSION
# ---------------------------------------------------------
logreg = LogisticRegression(max_iter=1000, random_state=42)
logreg.fit(X_train_scaled, y_train)
y_pred_lr = logreg.predict(X_test_scaled)
y_prob_lr = logreg.predict_proba(X_test_scaled)[:, 1]

cv_lr = cross_val_score(LogisticRegression(max_iter=1000, random_state=42),
                         X_train_scaled, y_train, cv=StratifiedKFold(5), scoring="accuracy")

lr_metrics = {
    "accuracy": accuracy_score(y_test, y_pred_lr),
    "precision": precision_score(y_test, y_pred_lr),
    "recall": recall_score(y_test, y_pred_lr),
    "f1": f1_score(y_test, y_pred_lr),
    "roc_auc": roc_auc_score(y_test, y_prob_lr),
    "cv_mean_acc": cv_lr.mean(),
    "cv_std_acc": cv_lr.std(),
}

# Coefficients (feature importance proxy)
coef_df = pd.DataFrame({
    "Feature": X.columns,
    "Coefficient": logreg.coef_[0]
}).sort_values("Coefficient", key=abs, ascending=False)

# ---------------------------------------------------------
# 6. MODEL 2: RANDOM FOREST
# ---------------------------------------------------------
rf = RandomForestClassifier(n_estimators=200, max_depth=6, random_state=42, min_samples_leaf=3)
rf.fit(X_train, y_train)  # tree-based model doesn't need scaling
y_pred_rf = rf.predict(X_test)
y_prob_rf = rf.predict_proba(X_test)[:, 1]

cv_rf = cross_val_score(RandomForestClassifier(n_estimators=200, max_depth=6, random_state=42, min_samples_leaf=3),
                         X_train, y_train, cv=StratifiedKFold(5), scoring="accuracy")

rf_metrics = {
    "accuracy": accuracy_score(y_test, y_pred_rf),
    "precision": precision_score(y_test, y_pred_rf),
    "recall": recall_score(y_test, y_pred_rf),
    "f1": f1_score(y_test, y_pred_rf),
    "roc_auc": roc_auc_score(y_test, y_prob_rf),
    "cv_mean_acc": cv_rf.mean(),
    "cv_std_acc": cv_rf.std(),
}

feat_imp = pd.DataFrame({
    "Feature": X.columns,
    "Importance": rf.feature_importances_
}).sort_values("Importance", ascending=False)

results["lr_metrics"] = {k: round(float(v), 4) for k, v in lr_metrics.items()}
results["rf_metrics"] = {k: round(float(v), 4) for k, v in rf_metrics.items()}
results["lr_coefficients"] = coef_df.round(4).to_dict(orient="records")
results["rf_importances"] = feat_imp.round(4).to_dict(orient="records")

# ---------------------------------------------------------
# 7. CONFUSION MATRICES
# ---------------------------------------------------------
fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))
for ax, (name, y_pred) in zip(axes, [("Logistic Regression", y_pred_lr), ("Random Forest", y_pred_rf)]):
    cm = confusion_matrix(y_test, y_pred)
    sns.heatmap(cm, annot=True, fmt="d", cmap="Blues", ax=ax,
                xticklabels=["No Diabetes", "Diabetes"], yticklabels=["No Diabetes", "Diabetes"],
                cbar=False, annot_kws={"fontsize": 13, "fontweight": "bold"})
    ax.set_title(name)
    ax.set_xlabel("Predicted")
    ax.set_ylabel("Actual")
plt.tight_layout()
plt.savefig(f"{FIG}/confusion_matrices.png", dpi=150)
plt.close()

# ---------------------------------------------------------
# 8. ROC CURVES
# ---------------------------------------------------------
fig, ax = plt.subplots(figsize=(6, 5))
for name, y_prob, color in [("Logistic Regression", y_prob_lr, PALETTE[0]),
                              ("Random Forest", y_prob_rf, PALETTE[1])]:
    fpr, tpr, _ = roc_curve(y_test, y_prob)
    auc = roc_auc_score(y_test, y_prob)
    ax.plot(fpr, tpr, label=f"{name} (AUC = {auc:.3f})", color=color, linewidth=2)
ax.plot([0, 1], [0, 1], linestyle="--", color="gray", linewidth=1)
ax.set_xlabel("False Positive Rate")
ax.set_ylabel("True Positive Rate")
ax.set_title("ROC Curve Comparison")
ax.legend(loc="lower right")
plt.tight_layout()
plt.savefig(f"{FIG}/roc_curves.png", dpi=150)
plt.close()

# ---------------------------------------------------------
# 9. FEATURE IMPORTANCE (Random Forest)
# ---------------------------------------------------------
fig, ax = plt.subplots(figsize=(7, 5))
feat_imp_sorted = feat_imp.sort_values("Importance")
ax.barh(feat_imp_sorted["Feature"], feat_imp_sorted["Importance"], color=PALETTE[2])
ax.set_xlabel("Importance")
ax.set_title("Random Forest Feature Importance")
plt.tight_layout()
plt.savefig(f"{FIG}/feature_importance.png", dpi=150)
plt.close()

# ---------------------------------------------------------
# 10. MODEL COMPARISON BAR CHART
# ---------------------------------------------------------
metrics_names = ["accuracy", "precision", "recall", "f1", "roc_auc"]
fig, ax = plt.subplots(figsize=(8, 5))
x = np.arange(len(metrics_names))
width = 0.35
ax.bar(x - width/2, [lr_metrics[m] for m in metrics_names], width, label="Logistic Regression", color=PALETTE[0])
ax.bar(x + width/2, [rf_metrics[m] for m in metrics_names], width, label="Random Forest", color=PALETTE[1])
ax.set_xticks(x)
ax.set_xticklabels(["Accuracy", "Precision", "Recall", "F1-Score", "ROC-AUC"])
ax.set_ylim(0, 1)
ax.set_title("Model Performance Comparison")
ax.legend()
for i, m in enumerate(metrics_names):
    ax.text(i - width/2, lr_metrics[m] + 0.02, f"{lr_metrics[m]:.2f}", ha="center", fontsize=8)
    ax.text(i + width/2, rf_metrics[m] + 0.02, f"{rf_metrics[m]:.2f}", ha="center", fontsize=8)
plt.tight_layout()
plt.savefig(f"{FIG}/model_comparison.png", dpi=150)
plt.close()

# ---------------------------------------------------------
# SAVE RESULTS JSON
# ---------------------------------------------------------
with open(f"{BASE}/results.json", "w") as f:
    json.dump(results, f, indent=2, default=str)

print(json.dumps(results, indent=2, default=str))
print("\nDONE. Figures saved to", FIG)
