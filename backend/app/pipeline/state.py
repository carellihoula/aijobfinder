from typing import Annotated, Optional, TypedDict

from langgraph.graph.message import add_messages


class PipelineState(TypedDict):
    pdf_path: str
    cv_text: str
    cv_json: Optional[dict]  # structured CV data as plain dict (from cv_structurer)
    user_keywords: list[str]
    keywords: list[str]
    # Search filters (user-provided at upload time)
    # Priority: user_locations > cv_json.location > no filter (all France)
    user_locations: list[str]   # explicit location from profile config
    contract_type: str          # cdi | cdd | stage | alternance | freelance | temps_partiel | ""
    remote: bool                # True = remote only
    date_posted: str            # today | 3days | week | month | "" (all)
    experience_level: str       # junior | mid | senior | ""
    # Retry loop
    failed_keywords: list[str]  # keywords that returned 0 results
    search_attempts: int        # number of API fallback attempts so far
    # Pipeline outputs
    jobs: list[dict]
    filtered_jobs: list[dict]
    matches: list[dict]
    final_report: str
    messages: Annotated[list, add_messages]