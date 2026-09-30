from typing import List, Optional, Union

from pydantic import BaseModel


class ArticleCreate(BaseModel):
    url: Optional[str] = None
    title: str
    summary: Optional[str] = ""
    content: Optional[str] = ""
    site_name: Optional[str] = ""
    author: Optional[str] = ""
    category: Optional[str] = "Tech & IA"
    tags: Optional[Union[List[str], str]] = ""
    notes: Optional[str] = ""
    image_url: Optional[str] = ""
    is_favorite: Optional[bool] = False


class ArticleUpdate(BaseModel):
    title: Optional[str] = None
    summary: Optional[str] = None
    content: Optional[str] = None
    site_name: Optional[str] = None
    author: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[Union[List[str], str]] = None
    notes: Optional[str] = None
    image_url: Optional[str] = None
    is_favorite: Optional[bool] = None
    is_archived: Optional[bool] = None


class ExtractRequest(BaseModel):
    url: str


class SentimentReportCreate(BaseModel):
    entity: str
    sentiment_score: int
    sentiment_label: str
    summary: str
    pros: Optional[List[str]] = []
    cons: Optional[List[str]] = []
    sources: Optional[List[dict]] = []
