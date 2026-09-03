from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.config import settings
from app.cv.schemas import CVSchema
from app.logger import get_logger
from app.observability.langfuse_client import get_langfuse_callbacks
from app.pipeline.state import PipelineState

logger = get_logger(__name__)

SYSTEM_PROMPT = """\
You are an expert CV parser.
Extract ALL information from the CV text and return it as structured data.

Rules:
- Be exhaustive with skills (languages, frameworks, tools, soft skills).
- For each experience, extract title, company, dates, and a short description.
- Detect all spoken languages and their level (A1 to C2 or native).
- List hobbies/interests if mentioned.
- Infer the seniority level from total experience and roles.
- If a field is not found in the CV, leave it as null or empty list.
- Set is_cv to false if the text is clearly not a CV/resume at all (an
  invoice, a random letter, an unrelated document, gibberish) - don't force
  a match just because a few fields could technically be filled in.\
"""


class NotACVError(ValueError):
    """Raised when the uploaded document's extracted text isn't actually a
    CV - caught specifically in worker/tasks.py to surface a clear,
    user-facing message instead of the generic pipeline-failure one."""


async def cv_structurer_node(state: PipelineState) -> dict:
    """Node 2 - Force the LLM to return a strict CVSchema JSON via structured output."""

    llm = ChatOpenAI(
        model=settings.OPENAI_MODEL_LIGHT,
        temperature=0,
        api_key=settings.OPENAI_API_KEY,
        callbacks=get_langfuse_callbacks(),
    )

    # with_structured_output activates OpenAI function-calling:
    # the model cannot return free text - only a valid CVSchema object.
    structured_llm = llm.with_structured_output(CVSchema)

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=f"Parse this CV and extract all information:\n\n{state['cv_text']}"),
    ]

    logger.info("[cv_structurer] Structuring CV (%d chars) ...", len(state["cv_text"]))
    result: CVSchema = await structured_llm.ainvoke(messages)

    # Belt and suspenders: trust the LLM's own is_cv judgment, but also treat
    # a schema that came back completely empty (no name, no skills, no
    # experiences, no roles) as "not a CV" even if the model didn't flag it -
    # a real CV, however thin, always has at least one of these.
    looks_empty = not (result.full_name or result.skills or result.experiences or result.roles)
    if not result.is_cv or looks_empty:
        logger.warning("[cv_structurer] Document rejected - doesn't look like a CV")
        raise NotACVError("NOT_A_CV")

    logger.info(
        "[cv_structurer] Parsed - name=%s, skills=%d, experiences=%d, level=%s",
        result.full_name or "unknown",
        len(result.skills),
        len(result.experiences),
        result.level,
    )
    return {"cv_json": result.model_dump()}