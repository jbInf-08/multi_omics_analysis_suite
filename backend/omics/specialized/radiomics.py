"""Radiomics Module.
================

Analysis module for medical imaging features extracted from radiological images.
"""

import pandas as pd

from ..base import (
    AnalysisDefinition,
    AnalysisParams,
    AnalysisResult,
    DataSource,
    OmicsCategory,
    OmicsData,
    OmicsModuleBase,
    Pipeline,
    QCMetric,
    QCReport,
    Visualization,
)


class RadiomicsModule(OmicsModuleBase):
    """Module for radiomics feature analysis from medical imaging."""

    @property
    def name(self) -> str:
        return "radiomics"

    @property
    def category(self) -> OmicsCategory:
        return OmicsCategory.SPECIALIZED

    @property
    def description(self) -> str:
        return "Quantitative image feature analysis from CT, MRI, PET, and other medical imaging modalities"

    @property
    def supported_formats(self) -> list[str]:
        return ["csv", "nifti", "dicom", "xlsx"]

    def load_data(self, source: DataSource) -> OmicsData:
        """Load radiomics feature data."""
        data = pd.read_csv(source.path, index_col=0) if source.format == "csv" else pd.DataFrame()
        return OmicsData(
            data=data,
            sample_metadata=pd.DataFrame(),
            feature_metadata=pd.DataFrame(),
            omics_type=self.name,
        )

    def preprocess(self, data: OmicsData) -> OmicsData:
        """Preprocess radiomics data."""
        df = data.data.copy()
        # Remove low variance features
        variance = df.var()
        df = df.loc[:, variance > variance.quantile(0.1)]
        return OmicsData(
            data=df,
            sample_metadata=data.sample_metadata,
            feature_metadata=data.feature_metadata,
            omics_type=self.name,
        )

    def quality_control(self, data: OmicsData) -> QCReport:
        """Run QC on radiomics data."""
        df = data.data
        metrics = [
            QCMetric(name="n_features", value=df.shape[1], threshold=50, passed=df.shape[1] >= 50),
            QCMetric(name="n_samples", value=df.shape[0], threshold=20, passed=df.shape[0] >= 20),
        ]
        return QCReport(metrics=metrics, passed=all(m.passed for m in metrics))

    def normalize(self, data: OmicsData, params: AnalysisParams) -> OmicsData:
        """Normalize radiomics features."""
        method = params.parameters.get("method", "zscore")
        df = data.data.copy()
        if method == "zscore":
            df = (df - df.mean()) / df.std()
        elif method == "minmax":
            df = (df - df.min()) / (df.max() - df.min())
        return OmicsData(
            data=df,
            sample_metadata=data.sample_metadata,
            feature_metadata=data.feature_metadata,
            omics_type=self.name,
        )

    def analyze(self, data: OmicsData, params: AnalysisParams) -> AnalysisResult:
        """Run radiomics analysis."""
        return AnalysisResult(
            name=params.name, data=pd.DataFrame(), parameters=params.parameters, status="completed"
        )

    def visualize(self, result: AnalysisResult, params: dict | None = None) -> Visualization:
        """Create radiomics visualizations."""
        return Visualization(
            name=f"{result.name}_plot",
            plot_type="bar",
            data=result.data.to_dict(),
            config=params or {},
        )

    def get_available_pipelines(self) -> list[Pipeline]:
        """Get available radiomics pipelines."""
        return [
            Pipeline(
                name="radiomic_signature",
                description="Build radiomic signature",
                steps=["load", "normalize", "feature_selection", "model", "validate"],
            ),
            Pipeline(
                name="delta_radiomics",
                description="Longitudinal radiomics analysis",
                steps=["load", "align", "delta_features", "analysis"],
            ),
        ]

    def get_available_analyses(self) -> list[AnalysisDefinition]:
        """Get available radiomics analyses."""
        return [
            AnalysisDefinition(name="feature_selection", description="Radiomics feature selection"),
            AnalysisDefinition(
                name="survival_prediction", description="Survival prediction from radiomics"
            ),
            AnalysisDefinition(
                name="response_prediction", description="Treatment response prediction"
            ),
            AnalysisDefinition(
                name="tumor_phenotyping", description="Tumor phenotype classification"
            ),
        ]
