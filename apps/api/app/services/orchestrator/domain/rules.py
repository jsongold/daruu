"""Domain rules for orchestrator loop control.

This module contains pure domain logic for:
- Termination conditions (when to stop the pipeline)
- Improvement rate calculations (detecting convergence)
- Issue scoring (for comparing iterations)

These functions are pure and have no external dependencies,
making them easy to test and reason about.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Sequence

from app.config import OrchestratorConfig, get_issue_scoring_config
from app.models import Issue, IssueSeverity, JobContext


class TerminationAction(str, Enum):
    """Action to take when termination is checked."""

    DONE = "done"  # Job completed successfully
    BLOCKED = "blocked"  # Job blocked, cannot proceed
    ASK = "ask"  # Need user input
    MANUAL = "manual"  # Need manual intervention
    CONTINUE = "continue"  # Continue processing


@dataclass(frozen=True)
class TerminationCondition:
    """Immutable termination condition result.

    This represents the outcome of checking whether a job should terminate.
    The frozen=True ensures immutability.
    """

    should_terminate: bool
    reason: str
    action: TerminationAction

    def to_dict(self) -> dict[str, str | bool]:
        """Convert to dictionary for serialization."""
        return {
            "should_terminate": self.should_terminate,
            "reason": self.reason,
            "action": self.action.value,
        }


def check_termination(
    job_context: JobContext,
    config: OrchestratorConfig,
    previous_issues: Sequence[Issue] | None = None,
) -> TerminationCondition:
    """Check if job should terminate.

    Conditions checked (in order):
    1. Issue == 0 AND confidence >= threshold -> done
    2. Max iterations exceeded -> blocked
    3. Critical issues -> manual
    4. No improvement (improvement rate below threshold) -> ask/manual
    5. Otherwise -> continue

    Args:
        job_context: Current job state.
        config: Orchestrator configuration with thresholds.
        previous_issues: Issues from previous iteration for improvement tracking.

    Returns:
        TerminationCondition with should_terminate, reason, and action.
    """
    # Condition 1: All issues resolved and confidence met
    if _is_job_complete(job_context, config):
        return TerminationCondition(
            should_terminate=True,
            reason="All issues resolved and confidence threshold met",
            action=TerminationAction.DONE,
        )

    # Condition 2: Max iterations exceeded
    if job_context.iteration_count >= config.max_iterations:
        return TerminationCondition(
            should_terminate=True,
            reason=f"Maximum iterations ({config.max_iterations}) reached",
            action=TerminationAction.BLOCKED,
        )

    # Condition 3: Critical issues require manual intervention
    critical_issues = _get_critical_issues(job_context.issues)
    if critical_issues:
        return TerminationCondition(
            should_terminate=True,
            reason=f"Critical issue requires manual intervention: {critical_issues[0].message}",
            action=TerminationAction.MANUAL,
        )

    # Condition 4: No improvement (only check if we have previous issues to compare)
    if previous_issues is not None and job_context.iteration_count > 0:
        improvement_rate = calculate_improvement_rate(
            list(previous_issues),
            list(job_context.issues),
        )
        if improvement_rate < config.min_improvement_rate:
            return TerminationCondition(
                should_terminate=True,
                reason=f"Improvement rate too low: {improvement_rate:.2%}",
                action=TerminationAction.ASK,
            )

    # Condition 5: Continue processing
    return TerminationCondition(
        should_terminate=False,
        reason="Termination conditions not met, continue processing",
        action=TerminationAction.CONTINUE,
    )


def _is_job_complete(job_context: JobContext, config: OrchestratorConfig) -> bool:
    """Check if job is complete (no issues and all fields meet confidence)."""
    # Must have no issues
    if job_context.issues:
        return False

    # All fields must meet confidence threshold
    for field in job_context.fields:
        if field.value is not None and field.confidence is not None:
            if field.confidence < config.confidence_threshold:
                return False

    return True


def _get_critical_issues(issues: Sequence[Issue]) -> list[Issue]:
    """Filter critical or high severity issues."""
    return [
        issue for issue in issues
        if issue.severity in (IssueSeverity.CRITICAL, IssueSeverity.HIGH)
    ]


def calculate_improvement_rate(
    previous_issues: list[Issue],
    current_issues: list[Issue],
) -> float:
    """Calculate improvement rate between iterations.

    Improvement is measured by:
    1. Reduction in total issue count
    2. Reduction in weighted issue score (severity-weighted)

    The improvement rate is the average of these two metrics.

    Args:
        previous_issues: Issues from previous iteration.
        current_issues: Issues from current iteration.

    Returns:
        Improvement rate between 0.0 and 1.0.
        - 1.0 means complete improvement (all issues resolved)
        - 0.0 means no improvement
        - Negative values are clamped to 0.0
    """
    if not previous_issues:
        # No previous issues to compare
        return 1.0 if not current_issues else 0.0

    # Calculate count-based improvement
    prev_count = len(previous_issues)
    curr_count = len(current_issues)
    count_improvement = (prev_count - curr_count) / prev_count if prev_count > 0 else 0.0

    # Calculate score-based improvement (weighted by severity)
    prev_score = calculate_issue_score(previous_issues)
    curr_score = calculate_issue_score(current_issues)
    score_improvement = (prev_score - curr_score) / prev_score if prev_score > 0 else 0.0

    # Average of both metrics, clamped to [0, 1]
    improvement = (count_improvement + score_improvement) / 2.0
    return max(0.0, min(1.0, improvement))


def calculate_issue_score(issues: Sequence[Issue]) -> float:
    """Calculate total weighted score for a list of issues.

    Weights are loaded from centralized configuration.
    Default weights:
    - CRITICAL: 10 points
    - HIGH: 5 points
    - ERROR: 5 points (alias for HIGH)
    - WARNING: 2 points
    - INFO: 1 point

    Args:
        issues: List of issues to score.

    Returns:
        Total weighted score.
    """
    scoring_config = get_issue_scoring_config()

    severity_weights = {
        IssueSeverity.CRITICAL: scoring_config.critical_weight,
        IssueSeverity.HIGH: scoring_config.high_weight,
        IssueSeverity.ERROR: scoring_config.high_weight,
        IssueSeverity.WARNING: scoring_config.warning_weight,
        IssueSeverity.INFO: scoring_config.info_weight,
    }

    return sum(
        severity_weights.get(issue.severity, scoring_config.info_weight)
        for issue in issues
    )
