"""LLM-Powered Insights Module.
===========================

Generate insights from analysis results using LLMs.
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


def utc_now() -> datetime:
    """Return current UTC time."""
    return datetime.now(timezone.utc)


from backend.ai.llm_providers import LLMConfig, LLMProvider, get_provider

logger = logging.getLogger(__name__)


class InsightType(str, Enum):
    """Types of insights."""

    SUMMARY = "summary"
    FINDING = "finding"
    RECOMMENDATION = "recommendation"
    WARNING = "warning"
    INTERPRETATION = "interpretation"
    HYPOTHESIS = "hypothesis"


class InsightPriority(str, Enum):
    """Priority levels for insights."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class AnalysisInsight:
    """A single analysis insight."""

    insight_type: InsightType
    title: str
    description: str
    priority: InsightPriority
    evidence: list[str] = field(default_factory=list)
    related_features: list[str] = field(default_factory=list)
    confidence: float = 0.8
    generated_at: datetime = field(default_factory=utc_now)


@dataclass
class InsightReport:
    """Collection of insights from an analysis."""

    analysis_type: str
    insights: list[AnalysisInsight]
    summary: str
    generated_at: datetime = field(default_factory=utc_now)
    model_used: str = ""
    raw_response: str | None = None


class InsightGenerator:
    """Generate insights from analysis results using LLMs.

    Automatically interprets results and generates
    actionable insights and recommendations.
    """

    def __init__(
        self,
        config: LLMConfig | None = None,
        provider: LLMProvider | None = None,
    ):
        """Initialize insight generator.

        Args:
            config: LLM configuration
            provider: Pre-configured LLM provider

        """
        if provider:
            self.provider = provider
        elif config:
            self.provider = get_provider(config)
        else:
            self.provider = get_provider(LLMConfig(provider="openai"))

    async def generate_insights(
        self,
        analysis_type: str,
        results: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> InsightReport:
        """Generate insights from analysis results.

        Args:
            analysis_type: Type of analysis
            results: Analysis results dictionary
            context: Additional context

        Returns:
            InsightReport

        """
        prompt = self._build_insight_prompt(analysis_type, results, context)

        system_prompt = """You are an expert bioinformatics analyst generating insights from analysis results.

Your task is to:
1. Identify key findings in the results
2. Provide biological interpretations
3. Generate actionable recommendations
4. Flag any potential issues or warnings
5. Suggest follow-up analyses

Respond in JSON format with the following structure:
{
    "summary": "Overall summary of findings",
    "insights": [
        {
            "type": "finding|recommendation|warning|interpretation|hypothesis",
            "title": "Brief title",
            "description": "Detailed description",
            "priority": "high|medium|low",
            "evidence": ["Supporting evidence points"],
            "related_features": ["Gene names or features involved"],
            "confidence": 0.8
        }
    ]
}"""

        try:
            response = await self.provider.generate(
                prompt,
                system_prompt=system_prompt,
                temperature=0.3,  # Lower temperature for more consistent output
            )

            # Parse JSON response
            insights = self._parse_insights(response.content, analysis_type)
            insights.model_used = response.model
            insights.raw_response = response.content

            return insights

        except Exception as e:
            logger.error(f"Insight generation failed: {e}")
            return InsightReport(
                analysis_type=analysis_type,
                insights=[
                    AnalysisInsight(
                        insight_type=InsightType.WARNING,
                        title="Insight Generation Failed",
                        description=f"Could not generate insights: {str(e)}",
                        priority=InsightPriority.MEDIUM,
                    )
                ],
                summary="Insight generation encountered an error.",
            )

    def _build_insight_prompt(
        self,
        analysis_type: str,
        results: dict[str, Any],
        context: dict[str, Any] | None,
    ) -> str:
        """Build the prompt for insight generation."""
        prompt_parts = [
            f"Analysis Type: {analysis_type}",
            "",
            "Results:",
        ]

        # Format results
        for key, value in results.items():
            if isinstance(value, (int, float)) or isinstance(value, list) and len(value) <= 20:
                prompt_parts.append(f"- {key}: {value}")
            elif isinstance(value, dict):
                prompt_parts.append(f"- {key}:")
                for k, v in list(value.items())[:10]:
                    prompt_parts.append(f"  - {k}: {v}")

        # Add context
        if context:
            prompt_parts.extend(
                [
                    "",
                    "Additional Context:",
                ]
            )
            for key, value in context.items():
                prompt_parts.append(f"- {key}: {value}")

        prompt_parts.extend(
            [
                "",
                "Please analyze these results and generate insights.",
            ]
        )

        return "\n".join(prompt_parts)

    def _parse_insights(
        self,
        response: str,
        analysis_type: str,
    ) -> InsightReport:
        """Parse LLM response into InsightReport."""
        try:
            # Extract JSON from response
            json_start = response.find("{")
            json_end = response.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                data = json.loads(json_str)
            else:
                raise ValueError("No JSON found in response")

            insights = []
            for item in data.get("insights", []):
                insight_type = InsightType.FINDING
                type_str = item.get("type", "finding").lower()
                if type_str in [e.value for e in InsightType]:
                    insight_type = InsightType(type_str)

                priority = InsightPriority.MEDIUM
                priority_str = item.get("priority", "medium").lower()
                if priority_str in [e.value for e in InsightPriority]:
                    priority = InsightPriority(priority_str)

                insights.append(
                    AnalysisInsight(
                        insight_type=insight_type,
                        title=item.get("title", ""),
                        description=item.get("description", ""),
                        priority=priority,
                        evidence=item.get("evidence", []),
                        related_features=item.get("related_features", []),
                        confidence=item.get("confidence", 0.8),
                    )
                )

            return InsightReport(
                analysis_type=analysis_type,
                insights=insights,
                summary=data.get("summary", ""),
            )

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse JSON response: {e}")
            # Return raw response as single insight
            return InsightReport(
                analysis_type=analysis_type,
                insights=[
                    AnalysisInsight(
                        insight_type=InsightType.INTERPRETATION,
                        title="Analysis Interpretation",
                        description=response,
                        priority=InsightPriority.MEDIUM,
                    )
                ],
                summary=response[:500] if len(response) > 500 else response,
            )

    async def generate_de_insights(
        self,
        de_results: dict[str, Any],
        tumor_type: str | None = None,
    ) -> InsightReport:
        """Generate insights for differential expression results.

        Args:
            de_results: DE analysis results
            tumor_type: Cancer type for context

        Returns:
            InsightReport

        """
        context = {}
        if tumor_type:
            context["tumor_type"] = tumor_type

        return await self.generate_insights(
            "differential_expression",
            de_results,
            context,
        )

    async def generate_pathway_insights(
        self,
        pathway_results: dict[str, Any],
    ) -> InsightReport:
        """Generate insights for pathway analysis."""
        return await self.generate_insights(
            "pathway_enrichment",
            pathway_results,
        )

    async def generate_survival_insights(
        self,
        survival_results: dict[str, Any],
    ) -> InsightReport:
        """Generate insights for survival analysis."""
        return await self.generate_insights(
            "survival_analysis",
            survival_results,
        )

    async def generate_biomarker_insights(
        self,
        biomarker_results: dict[str, Any],
    ) -> InsightReport:
        """Generate insights for biomarker discovery."""
        return await self.generate_insights(
            "biomarker_discovery",
            biomarker_results,
        )

    async def summarize_multi_analysis(
        self,
        analyses: dict[str, dict[str, Any]],
    ) -> str:
        """Generate a summary across multiple analyses.

        Args:
            analyses: Dict mapping analysis names to results

        Returns:
            Comprehensive summary

        """
        prompt = "Summarize the following multi-omics analyses and identify overarching themes:\n\n"

        for name, results in analyses.items():
            prompt += f"## {name}\n"
            for key, value in list(results.items())[:10]:
                prompt += f"- {key}: {value}\n"
            prompt += "\n"

        prompt += """
Please provide:
1. An integrated summary of all findings
2. Common themes across analyses
3. Potential biological mechanisms
4. Key recommendations for follow-up"""

        response = await self.provider.generate(prompt)
        return response.content
