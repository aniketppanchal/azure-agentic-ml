from typing import Literal

from pydantic import BaseModel, Field, field_validator


class ModelTrainingConfig(BaseModel):
    request_id: str
    task_type: Literal["regression", "classification"] = Field(
        description="Type of machine learning task",
    )
    target: str = Field(
        description="Target column name",
    )
    features: str = Field(
        default="",
        description="Comma-separated feature column names",
    )
    model_type: Literal["auto", "random_forest", "svm", "linear"] = Field(
        default="auto",
        description="Type of machine learning model",
    )
    n_estimators: int = Field(
        default=100,
        gt=0,
        le=1000,
        description="Number of estimators for random forest",
    )
    svm_kernel: Literal["linear", "poly", "rbf", "sigmoid"] = Field(
        default="rbf",
        description="Kernel type for SVM",
    )
    missing_strategy: Literal["drop", "mean", "median", "most_frequent"] = Field(
        default="median",
        description="Strategy for handling missing values",
    )
    remove_outliers: bool = Field(
        default=False,
        description="Flag to remove outliers",
    )
    scaler_type: Literal["none", "standard", "minmax", "robust"] = Field(
        default="none",
        description="Type of feature scaler",
    )
    test_size: float = Field(
        default=0.2,
        ge=0.1,
        lt=0.5,
        description="Proportion of dataset for testing",
    )
    random_state: int = Field(
        default=42,
        ge=0,
        description="Random seed for reproducibility",
    )

    @field_validator("target")
    def validate_target(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Target column name cannot be empty")
        return v.strip()

    @field_validator("features")
    def validate_features(cls, v: str) -> str:
        return v.strip()
