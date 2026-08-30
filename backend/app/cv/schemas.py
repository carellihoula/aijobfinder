from typing import List, Literal, Optional

from pydantic import BaseModel, EmailStr, Field


class Experience(BaseModel):
    title: Optional[str] = None
    company: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    description: Optional[str] = None


class Education(BaseModel):
    degree: Optional[str] = None
    school: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class Language(BaseModel):
    name: str
    level: Optional[Literal["A1", "A2", "B1", "B2", "C1", "C2", "native"]] = None


class Hobby(BaseModel):
    name: str


class CVSchema(BaseModel):
    """Structured CV extracted from raw text. All fields are optional to handle incomplete CVs."""

    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    summary: Optional[str] = None

    skills: List[str] = Field(default_factory=list)
    experiences: List[Experience] = Field(default_factory=list)
    education: List[Education] = Field(default_factory=list)
    languages: List[Language] = Field(default_factory=list)
    hobbies: List[Hobby] = Field(default_factory=list)

    # Derived fields filled by the LLM
    roles: List[str] = Field(default_factory=list, description="Job titles held or targeted")
    experience_years: int = Field(default=0, ge=0, description="Total years of experience")
    level: Literal["junior", "mid", "senior", "lead", "principal"] = Field(
        default="mid", description="Inferred seniority level"
    )
    is_cv: bool = Field(
        default=True,
        description=(
            "False if the input text is clearly not a CV/resume - e.g. an "
            "invoice, a random document, an unrelated letter, gibberish. "
            "True whenever it's genuinely a CV, even a very short or "
            "incomplete one."
        ),
    )