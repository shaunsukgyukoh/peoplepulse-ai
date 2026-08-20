# ruff: noqa: E501
from __future__ import annotations

import pandas as pd
import pandera.pandas as pa
from pandera.typing import Series


class JobSiteAccessSchema(pa.DataFrameModel):
    employee_name: Series[str] = pa.Field(nullable=False, str_length={"min_value": 1, "max_value": 128})
    department: Series[str] = pa.Field(nullable=False, str_length={"min_value": 1, "max_value": 256})
    total_access_time_text: Series[str] = pa.Field(nullable=True)
    site: Series[str] = pa.Field(nullable=False, str_length={"min_value": 1, "max_value": 512})
    title: Series[str] = pa.Field(nullable=True)
    access_duration_seconds: Series[float] = pa.Field(ge=0, le=86_400, nullable=False)
    access_date: Series[pd.Timestamp] = pa.Field(nullable=False)

    class Config:
        strict = True
        coerce = True


class WebSearchSchema(pa.DataFrameModel):
    employee_name: Series[str] = pa.Field(nullable=False, str_length={"min_value": 1, "max_value": 128})
    department: Series[str] = pa.Field(nullable=False, str_length={"min_value": 1, "max_value": 256})
    search_keyword_summary: Series[str] = pa.Field(nullable=True)
    query_text: Series[str] = pa.Field(nullable=True)
    search_term: Series[str] = pa.Field(nullable=True)
    search_site: Series[str] = pa.Field(nullable=True)
    searched_at: Series[pd.Timestamp] = pa.Field(nullable=False)

    class Config:
        strict = True
        coerce = True


class DocumentUsageSchema(pa.DataFrameModel):
    employee_name: Series[str] = pa.Field(nullable=False, str_length={"min_value": 1, "max_value": 128})
    department: Series[str] = pa.Field(nullable=False, str_length={"min_value": 1, "max_value": 256})
    usage_keyword_summary: Series[str] = pa.Field(nullable=True)
    keyword: Series[str] = pa.Field(nullable=True)
    document_name: Series[str] = pa.Field(nullable=True)
    action: Series[str] = pa.Field(nullable=True, str_length={"max_value": 64})
    occurred_at: Series[pd.Timestamp] = pa.Field(nullable=False)

    class Config:
        strict = True
        coerce = True
