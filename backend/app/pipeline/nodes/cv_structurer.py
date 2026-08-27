from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.config import settings
from app.cv.schemas import CVSchema
from app.logger import get_logger
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
- If a field is not found in the CV, leave it as null or empty list.\
"""


async def cv_structurer_node(state: PipelineState) -> dict:
    """Node 2 - Force the LLM to return a strict CVSchema JSON via structured output."""

    llm = ChatOpenAI(
        model=settings.OPENAI_MODEL,
        temperature=0,
        api_key=settings.OPENAI_API_KEY,
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

    logger.info(
        "[cv_structurer] Parsed - name=%s, skills=%d, experiences=%d, level=%s",
        result.full_name or "unknown",
        len(result.skills),
        len(result.experiences),
        result.level,
    )
    return {"cv_json": result.model_dump()}