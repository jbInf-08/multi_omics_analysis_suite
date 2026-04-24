"""Analysis Chatbot Module.
=======================

AI-powered chatbot for analysis assistance:
- Context-aware conversation
- Multi-omics analysis guidance
- Results interpretation
"""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


def utc_now() -> datetime:
    """Return current UTC time."""
    return datetime.now(timezone.utc)


from backend.ai.llm_providers import LLMConfig, LLMProvider, get_provider

logger = logging.getLogger(__name__)


class MessageRole(str, Enum):
    """Chat message roles."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


@dataclass
class ChatMessage:
    """A single chat message."""

    role: MessageRole
    content: str
    timestamp: datetime = field(default_factory=utc_now)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ChatSession:
    """A chat session with history."""

    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    messages: list[ChatMessage] = field(default_factory=list)
    context: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def add_message(self, role: MessageRole, content: str, **metadata):
        """Add a message to the session."""
        self.messages.append(
            ChatMessage(
                role=role,
                content=content,
                metadata=metadata,
            )
        )
        self.updated_at = utc_now()

    def get_messages_for_api(self) -> list[dict[str, str]]:
        """Get messages formatted for API calls."""
        return [{"role": msg.role.value, "content": msg.content} for msg in self.messages]

    def clear_history(self):
        """Clear conversation history."""
        self.messages = []
        self.updated_at = utc_now()


class AnalysisChatbot:
    """AI-powered chatbot for multi-omics analysis assistance.

    Provides:
    - Analysis guidance and recommendations
    - Results interpretation
    - Method explanations
    - Troubleshooting assistance
    """

    SYSTEM_PROMPT = """You are an expert bioinformatics assistant specializing in multi-omics data analysis.

Your expertise includes:
- Genomics, transcriptomics, proteomics, and metabolomics analysis
- Statistical analysis methods (differential expression, pathway analysis)
- Machine learning for biological data
- Cancer genomics and biomarker discovery
- Clinical data interpretation

When helping users:
1. Provide clear, accurate, and actionable guidance
2. Explain complex concepts in accessible terms
3. Suggest appropriate analysis methods for their data
4. Help interpret results in biological context
5. Recommend best practices and quality control steps
6. Cite relevant literature or resources when appropriate

If you don't know something, say so clearly rather than guessing.
Always prioritize scientific accuracy and reproducibility."""

    def __init__(
        self,
        config: LLMConfig | None = None,
        provider: LLMProvider | None = None,
    ):
        """Initialize analysis chatbot.

        Args:
            config: LLM configuration
            provider: Pre-configured LLM provider

        """
        if provider:
            self.provider = provider
        elif config:
            self.provider = get_provider(config)
        else:
            # Default to OpenAI
            self.provider = get_provider(LLMConfig(provider="openai"))

        self._sessions: dict[str, ChatSession] = {}

    def create_session(
        self,
        context: dict[str, Any] | None = None,
    ) -> ChatSession:
        """Create a new chat session.

        Args:
            context: Initial context (analysis results, data info, etc.)

        Returns:
            New ChatSession

        """
        session = ChatSession(context=context or {})

        # Add system message
        session.add_message(MessageRole.SYSTEM, self.SYSTEM_PROMPT)

        # Add context if provided
        if context:
            context_prompt = self._format_context(context)
            session.add_message(MessageRole.SYSTEM, context_prompt)

        self._sessions[session.session_id] = session
        return session

    def get_session(self, session_id: str) -> ChatSession | None:
        """Get an existing session by ID."""
        return self._sessions.get(session_id)

    async def chat(
        self,
        message: str,
        session_id: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> str:
        """Send a message and get a response.

        Args:
            message: User message
            session_id: Session ID (creates new if None)
            context: Additional context for this message

        Returns:
            Assistant response

        """
        # Get or create session
        if session_id:
            session = self.get_session(session_id)
            if session is None:
                session = self.create_session(context)
        else:
            session = self.create_session(context)

        # Add context if provided
        if context:
            context_info = self._format_context(context)
            enhanced_message = f"{context_info}\n\nUser question: {message}"
        else:
            enhanced_message = message

        # Add user message
        session.add_message(MessageRole.USER, enhanced_message)

        try:
            # Get response from LLM
            response = await self.provider.chat(session.get_messages_for_api())

            # Add assistant response
            session.add_message(
                MessageRole.ASSISTANT,
                response.content,
                usage=response.usage,
            )

            return response.content

        except Exception as e:
            logger.error(f"Chat error: {e}")
            error_msg = (
                "I apologize, but I encountered an error processing your request. Please try again."
            )
            session.add_message(MessageRole.ASSISTANT, error_msg)
            return error_msg

    async def ask_about_analysis(
        self,
        analysis_type: str,
        results: dict[str, Any],
        question: str | None = None,
    ) -> str:
        """Ask about analysis results.

        Args:
            analysis_type: Type of analysis (e.g., "differential_expression")
            results: Analysis results dictionary
            question: Specific question (optional)

        Returns:
            AI interpretation/response

        """
        context = {
            "analysis_type": analysis_type,
            "results": results,
        }

        if question:
            message = question
        else:
            message = (
                f"Please interpret these {analysis_type} results and highlight the key findings."
            )

        return await self.chat(message, context=context)

    async def get_method_recommendation(
        self,
        data_description: str,
        research_question: str,
    ) -> str:
        """Get method recommendations for analysis.

        Args:
            data_description: Description of the data
            research_question: Research question to address

        Returns:
            Recommended analysis methods

        """
        prompt = f"""Given the following data and research question, recommend appropriate analysis methods:

Data Description:
{data_description}

Research Question:
{research_question}

Please recommend:
1. Appropriate statistical/computational methods
2. Required preprocessing steps
3. Quality control considerations
4. Potential pitfalls to avoid
5. Relevant parameters or thresholds"""

        return await self.chat(prompt)

    async def explain_concept(
        self,
        concept: str,
        context: str | None = None,
        detail_level: str = "moderate",
    ) -> str:
        """Explain a bioinformatics concept.

        Args:
            concept: Concept to explain
            context: Additional context
            detail_level: "basic", "moderate", or "advanced"

        Returns:
            Explanation

        """
        prompt = f"""Please explain the concept of "{concept}" in the context of multi-omics analysis.

Detail level: {detail_level}
{f'Additional context: {context}' if context else ''}

Include:
1. Definition and key principles
2. Common applications in bioinformatics
3. Advantages and limitations
4. Practical considerations"""

        return await self.chat(prompt)

    def _format_context(self, context: dict[str, Any]) -> str:
        """Format context dictionary into a prompt."""
        parts = ["Current analysis context:"]

        if "analysis_type" in context:
            parts.append(f"- Analysis type: {context['analysis_type']}")

        if "data_info" in context:
            info = context["data_info"]
            parts.append(
                f"- Data: {info.get('n_samples', 'N/A')} samples, {info.get('n_features', 'N/A')} features"
            )
            if "data_type" in info:
                parts.append(f"- Data type: {info['data_type']}")

        if "results" in context:
            results = context["results"]
            parts.append("- Results summary:")

            if isinstance(results, dict):
                for key, value in list(results.items())[:10]:
                    if (
                        isinstance(value, (int, float, str))
                        or isinstance(value, list)
                        and len(value) <= 5
                    ):
                        parts.append(f"  - {key}: {value}")

        return "\n".join(parts)

    def get_analysis_prompts(self) -> dict[str, str]:
        """Get pre-defined prompts for common analysis tasks."""
        return {
            "interpret_de": "Interpret the differential expression results. What are the key findings?",
            "pathway_summary": "Summarize the pathway enrichment results. Which biological processes are most affected?",
            "biomarker_selection": "Based on the feature selection results, which biomarkers are most promising?",
            "survival_interpretation": "Interpret the survival analysis results. What is the prognostic significance?",
            "quality_check": "Evaluate the quality control metrics. Are there any concerns?",
            "next_steps": "Based on these results, what are the recommended next steps for analysis?",
        }
