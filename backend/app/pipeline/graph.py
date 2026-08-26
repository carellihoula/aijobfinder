from langgraph.graph import END, StateGraph

from app.pipeline.nodes.cortex_search import cortex_search_node
from app.pipeline.nodes.embeddings_filter import embeddings_filter_node
from app.pipeline.nodes.llm_reranker import llm_reranker_node
from app.pipeline.nodes.pdf_parser import pdf_parser_node
from app.pipeline.nodes.cv_structurer import cv_structurer_node
from app.pipeline.nodes.report_generator import report_generator_node
from app.pipeline.state import PipelineState


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


# ─── Pipeline 2: Search (on-demand) ───────────────────────────────────────────
# cortex_search → embeddings_filter → llm_reranker → report_generator
# The Cortex is the sole source of jobs — pre-populated by nightly ingestion crons.

def _build_search() -> StateGraph:
    graph = StateGraph(PipelineState)
    graph.add_node("cortex_search",     cortex_search_node)
    graph.add_node("embeddings_filter", embeddings_filter_node)
    graph.add_node("llm_reranker",      llm_reranker_node)
    graph.add_node("report_generator",  report_generator_node)

    graph.set_entry_point("cortex_search")
    graph.add_edge("cortex_search",     "embeddings_filter")
    graph.add_edge("embeddings_filter", "llm_reranker")
    graph.add_edge("llm_reranker",      "report_generator")
    graph.add_edge("report_generator",  END)

    return graph.compile()


profile_init_pipeline = _build_profile_init()
search_pipeline       = _build_search()
