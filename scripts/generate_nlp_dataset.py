from __future__ import annotations

from pathlib import Path

import pandas as pd

from peoplepulse.nlp.labels import LABELS


SINGLES: dict[str, list[str]] = {
    "satisfied": [
        "이번 배포는 일정대로 끝나서 좋네요.",
        "리뷰 피드백 덕분에 작업이 훨씬 수월했습니다.",
        "이번 협업 방식은 효율적이라 만족스럽습니다.",
        "지원 요청을 빨리 처리해 주셔서 감사합니다.",
        "요구사항이 명확해서 개발하기 편했습니다.",
        "이번 스프린트는 역할 분담이 잘 된 것 같습니다.",
        "새 프로세스가 이전보다 훨씬 편하네요.",
        "회의가 짧고 결정이 명확해서 좋았습니다.",
        "이번 업무는 배울 점도 많고 재미있었습니다.",
        "도움 주신 덕분에 문제를 빠르게 해결했습니다.",
    ],
    "neutral": [
        "오늘 오후 세 시에 프로젝트 회의가 있습니다.",
        "수정한 문서는 공유 폴더에 올려두었습니다.",
        "테스트 결과는 내일 오전에 전달하겠습니다.",
        "현재 버전은 2.4.1이고 배포 대상은 개발 서버입니다.",
        "회의록에 결정 사항 세 가지를 정리했습니다.",
        "이번 주 작업 목록을 티켓으로 등록했습니다.",
        "담당자 확인 후 일정 업데이트하겠습니다.",
        "자료는 엑셀 파일과 PDF 두 개입니다.",
        "점검은 오전 열 시부터 시작할 예정입니다.",
        "이 이슈는 다음 스프린트로 이동했습니다.",
    ],
    "frustrated": [
        "같은 오류가 계속 반복돼서 답답하네요.",
        "요구사항이 또 바뀌어서 다시 작업해야 합니다.",
        "승인이 계속 늦어져서 진행을 못 하고 있습니다.",
        "어제 수정한 걸 오늘 다시 원래대로 바꾸라고 하네요.",
        "계속 기다리기만 하니까 일이 진도가 안 나갑니다.",
        "환경이 자꾸 깨져서 테스트를 몇 번째 다시 하는지 모르겠습니다.",
        "이 문제 때문에 계속 막혀 있어서 너무 답답합니다.",
        "같은 내용을 여러 번 보고해야 해서 비효율적입니다.",
        "결정이 계속 미뤄져서 일정 잡기가 어렵네요.",
        "정리되지 않은 요청이 계속 들어와서 헷갈립니다.",
    ],
    "angry": [
        "이렇게 일정을 일방적으로 바꾸는 건 정말 화가 납니다.",
        "몇 번을 말했는데 또 같은 문제가 생겨서 화가 나네요.",
        "아무 설명 없이 책임을 넘기는 건 너무 화납니다.",
        "합의한 내용을 무시하고 진행한 건 납득하기 어렵고 화가 납니다.",
        "계속 이런 식으로 대응하면 정말 화날 수밖에 없습니다.",
        "준비도 안 된 상태에서 당장 하라는 건 너무 화가 납니다.",
        "문제를 알고도 방치한 건 정말 화나는 일입니다.",
        "매번 마지막 순간에 통보하는 방식은 화가 납니다.",
        "제가 하지 않은 일까지 제 책임이라고 하니 화가 납니다.",
        "같은 실수를 반복하면서 아무 조치도 없는 게 화납니다.",
    ],
    "dissatisfied": [
        "현재 업무 프로세스에는 만족하기 어렵습니다.",
        "이 방식은 비효율적이라 계속 유지하는 게 불만입니다.",
        "역할과 책임이 불명확한 점이 가장 불만스럽습니다.",
        "의사결정 과정이 투명하지 않아서 만족스럽지 않습니다.",
        "현재 지원 체계로는 업무하기 어렵다는 생각이 듭니다.",
        "업무 우선순위가 매번 바뀌는 점이 불만입니다.",
        "개선 요청을 여러 번 했지만 반영되지 않아 불만입니다.",
        "성과 기준이 명확하지 않은 점이 만족스럽지 않습니다.",
        "현재 협업 방식은 효율이 낮아서 불만이 있습니다.",
        "계속 같은 문제가 반복되는 조직 운영 방식이 아쉽습니다.",
    ],
    "overloaded": [
        "이번 주 업무량이 너무 많아서 일정 안에 끝내기 어렵습니다.",
        "오늘 처리해야 할 일이 너무 많이 쌓여 있습니다.",
        "동시에 세 프로젝트를 맡아서 여력이 없습니다.",
        "마감이 겹쳐서 지금 업무 부담이 너무 큽니다.",
        "추가 업무까지 들어오면 현재 인력으로 감당하기 어렵습니다.",
        "이번 달은 계속 야근해야 할 정도로 일이 많습니다.",
        "긴급 요청이 계속 들어와서 기존 업무를 처리할 시간이 없습니다.",
        "담당 범위가 너무 넓어서 하나씩 제대로 보기 어렵습니다.",
        "이번 주 일정은 이미 꽉 차서 새 요청을 받기 어렵습니다.",
        "현재 작업량으로는 품질과 마감을 동시에 맞추기 어렵습니다.",
    ],
    "conflict": [
        "이 부분은 개발팀과 기획팀 의견이 계속 충돌하고 있습니다.",
        "담당자와 우선순위에 대한 의견 차이가 큽니다.",
        "서로 합의하지 않은 상태에서 진행해서 갈등이 생겼습니다.",
        "회의에서 역할 범위를 두고 의견이 많이 부딪혔습니다.",
        "팀 간 책임 범위가 겹쳐서 계속 마찰이 있습니다.",
        "저와 담당자의 해결 방향이 달라 조율이 필요합니다.",
        "이 문제는 서로 책임이 누구인지 두고 의견이 갈립니다.",
        "협업 과정에서 커뮤니케이션 방식 때문에 마찰이 있었습니다.",
        "두 팀의 요구사항이 반대라 합의가 잘 안 되고 있습니다.",
        "업무 배분 문제로 팀 안에서 의견 충돌이 있었습니다.",
    ],
    "disengaged": [
        "요즘은 이 업무에 예전만큼 관심이 가지 않습니다.",
        "이 프로젝트에 더 이상 적극적으로 참여하고 싶은 마음이 적습니다.",
        "계속 같은 업무만 반복되니 몰입하기 어렵습니다.",
        "최근에는 회의에서 굳이 의견을 내지 않게 됩니다.",
        "업무 개선에 대해 예전처럼 적극적으로 제안하고 싶지는 않습니다.",
        "지금 맡은 일에는 동기부여가 잘 되지 않습니다.",
        "프로젝트 방향에 별로 관여하고 싶지 않은 상태입니다.",
        "최근에는 필요한 일만 최소한으로 처리하게 됩니다.",
        "이 업무에 대한 흥미가 이전보다 많이 줄었습니다.",
        "새로운 업무가 생겨도 적극적으로 맡고 싶지는 않습니다.",
    ],
}

MIXED: list[tuple[tuple[str, ...], str]] = [
    (("frustrated", "overloaded"), "요구사항이 계속 바뀌는데 마감은 그대로라 업무량도 많고 너무 답답합니다."),
    (("dissatisfied", "overloaded"), "인력은 그대로인데 업무만 계속 늘어나는 운영 방식이 불만입니다."),
    (("angry", "conflict"), "합의한 내용을 상대 팀이 일방적으로 바꿔서 지금 정말 화가 납니다."),
    (("frustrated", "conflict"), "팀마다 말이 달라 계속 조율만 하고 있어서 답답합니다."),
    (("dissatisfied", "disengaged"), "개선이 전혀 안 되는 걸 보니 이제는 이 업무에 적극적으로 관여하고 싶지 않습니다."),
    (("overloaded", "disengaged"), "업무가 계속 쌓이다 보니 요즘은 새로운 일을 맡고 싶은 의욕도 줄었습니다."),
    (("satisfied", "overloaded"), "업무량은 많지만 팀에서 잘 도와줘서 이번 협업 자체는 만족스럽습니다."),
    (("satisfied", "conflict"), "의견 차이는 있었지만 충분히 논의해서 잘 해결된 점은 만족스럽습니다."),
    (("frustrated", "dissatisfied"), "매번 같은 문제가 반복되는 프로세스라 답답하고 운영 방식도 불만입니다."),
    (("angry", "dissatisfied"), "사전 협의 없이 일정을 바꾸는 방식은 정말 화가 나고 불만입니다."),
    (("conflict", "overloaded"), "팀 간 조율까지 제가 맡게 되어 갈등 대응과 기존 업무를 동시에 처리하기 벅찹니다."),
    (("frustrated", "disengaged"), "계속 막히는 일만 반복되니 이제는 이 업무에 적극적으로 나서고 싶지 않습니다."),
]

PREFIXES = ["", "현재 상황은 ", "오늘 업무를 하면서 "]
SUFFIXES = ["", " 확인 부탁드립니다.", " 이 부분은 조정이 필요해 보입니다."]


def split_for(index: int) -> str:
    mod = index % 10
    if mod <= 6:
        return "train"
    if mod == 7:
        return "val"
    return "test"


def make_row(text: str, labels: tuple[str, ...], split: str, group_id: str) -> dict:
    row = {"text": text, "split": split, "group_id": group_id}
    row.update({label: int(label in labels) for label in LABELS})
    return row


def main() -> None:
    rows: list[dict] = []
    for label, messages in SINGLES.items():
        for idx, message in enumerate(messages):
            split = split_for(idx)
            for aug in range(3):
                text = f"{PREFIXES[aug]}{message}{SUFFIXES[aug]}".strip()
                rows.append(make_row(text, (label,), split, f"{label}-{idx:02d}"))

    for idx, (labels, message) in enumerate(MIXED):
        split = split_for(idx)
        for aug in range(3):
            text = f"{PREFIXES[aug]}{message}{SUFFIXES[2-aug]}".strip()
            rows.append(make_row(text, labels, split, f"mixed-{idx:02d}"))

    df = pd.DataFrame(rows)
    out = Path("data/synthetic/nlp/workplace_messages_v01.csv")
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False, encoding="utf-8-sig")
    print(f"[OK] wrote {len(df)} rows -> {out}")
    print(df.groupby("split").size().to_string())
    print("\\nLabel positives:")
    print(df[list(LABELS)].sum().to_string())


if __name__ == "__main__":
    main()
