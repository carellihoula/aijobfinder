from collections import Counter

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.config import settings
from app.logger import get_logger
from app.observability.langfuse_client import get_langfuse_callbacks
from app.pipeline.state import PipelineState

logger = get_logger(__name__)

SYSTEM_PROMPT = """\
You are a professional career advisor.
Generate a clear, structured job search report in Markdown for the candidate.

The report must include:
1. **Candidate Summary** - 2-3 sentences summarizing the profile
2. **Top Matches** - for each job: title, company, location, score, why it fits, matching skills, missing skills, apply link
3. **Skills Gap Analysis** - missing skills ranked by frequency across all matches
4. **Recommendation** - 2-3 actionable sentences: what to apply to first, what to work on

Rules:
- Write in the same language as the candidate's CV
- Be direct and concrete, no generic filler
- Format scores as X/10
- Use bullet points for skills
"""


def _format_cv_summary(cv: dict) -> str:
    lines = [
        f"Name: {cv.get('full_name', 'N/A')}",
        f"Level: {cv.get('level', 'N/A')} | Experience: {cv.get('experience_years', 0)} years",
        f"Roles: {', '.join(cv.get('roles', []))}",
        f"Skills: {', '.join(cv.get('skills', []))}",
    ]
    if cv.get("summary"):
        lines.append(f"Summary: {cv['summary']}")
    return "\n".join(lines)


def _format_matches(matches: list[dict]) -> str:
    lines = []
    for i, m in enumerate(matches, 1):
        job = m["job"]
        lines.append(
            f"\n[Match {i}]\n"
            f"Title: {job.get('title', 'N/A')}\n"
            f"Company: {job.get('company', 'N/A')}\n"
            f"Location: {job.get('location', 'N/A')}\n"
            f"URL: {job.get('url', 'N/A')}\n"
            f"Score: {m['score']}/10\n"
            f"Why it fits: {m['reason']}\n"
            f"Matching skills: {', '.join(m.get('matching_skills', []))}\n"
            f"Missing skills: {', '.join(m.get('missing_skills', []))}"
        )
    return "\n".join(lines)


def _skills_gap(matches: list[dict]) -> str:
    counter: Counter = Counter()
    for m in matches:
        for skill in m.get("missing_skills", []):
            counter[skill.strip()] += 1
    if not counter:
        return "No significant skills gaps identified."
    return "\n".join(
        f"- {skill} (missing in {count}/{len(matches)} offers)"
        for skill, count in counter.most_common(10)
    )


async def report_generator_node(state: PipelineState) -> dict:
    """Node 7 - Generate a full Markdown report from CV profile and ranked matches."""
    cv = state.get("cv_json") or {}
    matches = state.get("matches") or []

    logger.info("[report_generator] Generating report for %d matches ...", len(matches))

    llm = ChatOpenAI(
        model=settings.OPENAI_MODEL_LIGHT,
        temperature=0.3,
        api_key=settings.OPENAI_API_KEY,
        callbacks=get_langfuse_callbacks(),
    )

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=(
            f"## Candidate profile\n{_format_cv_summary(cv)}\n\n"
            f"## Ranked job matches\n{_format_matches(matches)}\n\n"
            f"## Skills gap (pre-computed)\n{_skills_gap(matches)}"
        )),
    ]

    response = await llm.ainvoke(messages)
    report: str = response.content

    logger.info("[report_generator] Report ready (%d chars)", len(report))
    return {"final_report": report}