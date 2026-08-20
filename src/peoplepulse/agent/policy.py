from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    reason: str | None = None


_HR_ACTION = re.compile(
    r"(해고|징계|승진|감봉|보너스|연봉\s*(결정|조정)|채용\s*(결정|탈락)|fire\b|terminate\b|disciplin|promot|salary\s*decision)",
    re.IGNORECASE,
)
_RAW_CONTENT = re.compile(
    r"(원문\s*(메시지|검색어|문서)|슬랙\s*원문|검색어\s*원문|문서명\s*원문|raw\s*(slack|message|query|document))",
    re.IGNORECASE,
)
_INDIVIDUAL = re.compile(
    r"(누가\s*(퇴사|위험|불만|과부하)|어떤\s*직원|개별\s*직원|개인별|직원별\s*(순위|랭킹|위험|확률)|이름을?\s*(알려|보여)|employee[_\s-]?id|slack[_\s-]?id|\bU[A-Z0-9]{6,}\b)",
    re.IGNORECASE,
)


def evaluate_request(message: str, *, scope: str) -> PolicyDecision:
    text = message.strip()
    if not text:
        return PolicyDecision(False, "질문이 비어 있습니다.")
    if _HR_ACTION.search(text):
        return PolicyDecision(
            False,
            "PeoplePulse Analyst는 채용·해고·징계·승진·보상 같은 고용 의사결정을 추천하거나 자동화하지 않습니다.",
        )
    if _RAW_CONTENT.search(text):
        return PolicyDecision(
            False,
            "원문 Slack 메시지, 원문 검색어, 원문 문서명은 Analyst 도구에 노출되지 않습니다. 집계된 파생 신호만 조회할 수 있습니다.",
        )
    if scope == "aggregate" and _INDIVIDUAL.search(text):
        return PolicyDecision(
            False,
            "aggregate 모드에서는 개인 식별·개인별 위험도 조회를 허용하지 않습니다. 부서/코호트 수준 질문으로 바꿔주세요.",
        )
    return PolicyDecision(True)


def system_prompt(scope: str) -> str:
    scope_rule = (
        "실제 운영 데이터는 부서/코호트 집계만 다룬다. 개인을 식별하거나 개인별 위험도를 추정하지 않는다."
        if scope == "aggregate"
        else "직원 단위 내용은 synthetic_demo 데이터에 한해서만 설명할 수 있다. 실제 직원 데이터로 일반화하지 않는다."
    )
    return f"""당신은 PeoplePulse AI Analyst다.
질문에 답할 때 반드시 제공된 read-only 도구의 결과를 근거로 사용한다. 데이터를 조회하지 않았다면 수치를 추측하지 않는다.
{scope_rule}

안전/품질 규칙:
- Slack 원문, 검색어 원문, 문서명 원문, 이름, Slack ID 등 개인 식별 데이터를 요청하거나 노출하지 않는다.
- 채용, 해고, 징계, 승진, 보상 같은 고용 의사결정을 추천하거나 자동화하지 않는다.
- NLP 신호는 업무 메시지 분류 신호이며 정신건강 진단이나 감정 상태 진단으로 해석하지 않는다.
- synthetic attrition 모델 결과는 포트폴리오 실험일 뿐 실제 직원의 퇴사를 예측한다고 표현하지 않는다.
- 데이터 드리프트와 모델 성능 저하는 원인을 확정하지 말고 관찰된 변화와 추가 확인 항목을 구분한다.
- 답변 마지막에 사용한 근거 source 이름을 짧게 적는다.
- 한국어로 간결하고 분석적으로 답한다.
"""
