from langgraph.graph import END, StateGraph

from app.pipeline.nodes.cortex_feed import cortex_feed_node
from app.pipeline.nodes.cortex_search import cortex_search_node
from app.pipeline.nodes.cv_structurer import cv_structurer_node
from app.pipeline.nodes.embeddings_filter import embeddings_filter_node
from app.pipeline.nodes.job_search import job_search_node
from app.pipeline.nodes.keyword_extractor import keyword_extractor_node
from app.pipeline.nodes.llm_reranker import llm_reranker_node
from app.pipeline.nodes.pdf_parser import pdf_parser_node
from app.pipeline.nodes.prepare_retry import prepare_retry_node
from app.pipeline.nodes.report_generator import report_generator_node
from app.pipeline.state import PipelineState

MAX_SEARCH_ATTEMPTS = 2


# ─── Shared routing helpers ───────────────────────────────────────────────────

def _route_after_job_search(state: PipelineState) -> str:
    if state.get("jobs"):
        return "cortex_feed"
    if (state.get("search_attempts") or 0) < MAX_SEARCH_ATTEMPTS:
        return "prepare_retry"
    return "report_generator"


def _route_after_cortex_search(state: PipelineState) -> str:
    """Cortex hit → bridge to embeddings_filter. Miss → API fallback."""
    return "cortex_bridge" if state.get("filtered_jobs") else "keyword_extractor"


async def _cortex_bridge_node(state: PipelineState) -> dict:
    """Move cortex results from filtered_jobs → jobs so embeddings_filter can consume them."""
    return {"jobs": state.get("filtered_jobs") or [], "filtered_jobs": []}


# ─── Pipeline 1: Profile init (upload, one-time) ──────────────────────────────
# pdf_parser → cv_structurer → END
# Fast extraction only — no job search.

def _build_profile_init() -> StateGraph:
    graph = StateGraph(PipelineState)
    graph.add_node("pdf_parser",    pdf_parser_node)
    graph.add_node("cv_structurer", cv_structurer_node)
    graph.set_entry_point("pdf_parser")
    graph.add_edge("pdf_parser",    "cv_structurer")
    graph.add_edge("cv_structurer", END)
    return graph.compile()


# ─── Pipeline 2: Search (on-demand, uses profile data) ────────────────────────
# cortex_search → [hit: bridge → embeddings_filter | miss: keyword_extractor → job_search]
#              → embeddings_filter → llm_reranker → report_generator

def _build_search() -> StateGraph:
    graph = StateGraph(PipelineState)

    graph.add_node("cortex_search",     cortex_search_node)
    graph.add_node("cortex_bridge",     _cortex_bridge_node)
    graph.add_node("keyword_extractor", keyword_extractor_node)
    graph.add_node("job_search",        job_search_node)
    graph.add_node("cortex_feed",       cortex_feed_node)
    graph.add_node("prepare_retry",     prepare_retry_node)
    graph.add_node("embeddings_filter", embeddings_filter_node)
    graph.add_node("llm_reranker",      llm_reranker_node)
    graph.add_node("report_generator",  report_generator_node)

    graph.set_entry_point("cortex_search")
    graph.add_conditional_edges(
        "cortex_search",
        _route_after_cortex_search,
        {"cortex_bridge": "cortex_bridge", "keyword_extractor": "keyword_extractor"},
    )
    graph.add_edge("cortex_bridge",     "embeddings_filter")
    graph.add_edge("keyword_extractor", "job_search")
    graph.add_conditional_edges(
        "job_search",
        _route_after_job_search,
        {
            "cortex_feed":      "cortex_feed",
            "prepare_retry":    "prepare_retry",
            "report_generator": "report_generator",
        },
    )
    graph.add_edge("cortex_feed",       "embeddings_filter")
    graph.add_edge("prepare_retry",     "keyword_extractor")
    graph.add_edge("embeddings_filter", "llm_reranker")
    graph.add_edge("llm_reranker",      "report_generator")
    graph.add_edge("report_generator",  END)

    return graph.compile()


profile_init_pipeline = _build_profile_init()
search_pipeline       = _build_search()