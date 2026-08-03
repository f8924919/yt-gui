"""`.github/workflows/update-binaries.yml` の PR 作成トークン設定に対する回帰テスト。

既定の GITHUB_TOKEN が作成した PR では他のワークフローが起動せず、必須チェック
（test / test-windows）が発火しないため PR をマージできない（#284）。これを避けるため
`peter-evans/create-pull-request` には fine-grained PAT（secret `PIN_UPDATE_TOKEN`）を
渡している。この `token:` 指定が将来失われると、CI 未発火の症状に静かに戻るだけで
既存テストは素通りしてしまうので、ワークフロー定義そのものを検証する。

secret 未設定時は GITHUB_TOKEN へフォールバックする（上流更新の検知・sha256 検証まで
止めないため）。フォールバックしたことが分からないと #284 の再発に気づけないので、
警告を出す仕組みが残っていることも併せて検証する。

仕様・運用手順: docs/build.md「PR 作成トークン（secret `PIN_UPDATE_TOKEN`）」
"""

from pathlib import Path
from typing import Any

import pytest
import yaml

WORKFLOW_PATH = (
    Path(__file__).parent.parent / ".github" / "workflows" / "update-binaries.yml"
)

CREATE_PR_ACTION = "peter-evans/create-pull-request"
TOKEN_SECRET = "PIN_UPDATE_TOKEN"
HAS_TOKEN_ENV = "HAS_PIN_UPDATE_TOKEN"


@pytest.fixture(scope="module")
def workflow() -> dict[str, Any]:
    """ワークフロー定義をパースして返す。"""
    with open(WORKFLOW_PATH, encoding="utf-8") as f:
        loaded = yaml.safe_load(f)
    assert isinstance(loaded, dict)
    return loaded


@pytest.fixture(scope="module")
def steps(workflow: dict[str, Any]) -> list[dict[str, Any]]:
    """`refresh` ジョブのステップ一覧を返す。"""
    return list(workflow["jobs"]["refresh"]["steps"])


@pytest.fixture(scope="module")
def create_pr_step(steps: list[dict[str, Any]]) -> dict[str, Any]:
    """`peter-evans/create-pull-request` ステップを返す。"""
    matched = [s for s in steps if str(s.get("uses", "")).startswith(CREATE_PR_ACTION)]
    assert len(matched) == 1, f"{CREATE_PR_ACTION} ステップが 1 つだけ存在すること"
    return matched[0]


@pytest.fixture(scope="module")
def warn_step(steps: list[dict[str, Any]]) -> dict[str, Any]:
    """PAT 未設定時に警告するステップを返す。

    ステップごと削除された場合はここで落ちる（後続の assert が空文字を見て
    素通りしないよう、探索を fixture 側に寄せている）。
    """
    matched = [s for s in steps if HAS_TOKEN_ENV in str(s.get("if", ""))]
    assert len(matched) == 1, "PAT 未設定を警告するステップが失われている"
    return matched[0]


def test_create_pr_step_uses_pat_secret(create_pr_step: dict[str, Any]) -> None:
    """PR 作成に fine-grained PAT の secret を渡していること（#284）。"""
    token = create_pr_step["with"]["token"]
    assert f"secrets.{TOKEN_SECRET}" in token


def test_create_pr_step_falls_back_to_github_token(
    create_pr_step: dict[str, Any],
) -> None:
    """secret 未設定時は GITHUB_TOKEN にフォールバックすること。

    失効中も上流更新の検知・検証と PR 作成自体は継続させる方針（#284）。
    """
    token = create_pr_step["with"]["token"]
    assert "||" in token, "フォールバックの `||` が失われている"
    assert "github.token" in token


def test_job_exposes_pat_presence_as_env_flag(workflow: dict[str, Any]) -> None:
    """job の env で secret の有無を真偽値として公開していること。

    警告ステップの `if` はこの env を経由する（`secrets` はステップの `if` で
    参照できないため）。env 定義が失われると `if` が常に偽になり、警告が二度と
    出ないまま #284 の症状へ静かに戻る。
    """
    env = workflow["jobs"]["refresh"]["env"]
    flag = env[HAS_TOKEN_ENV]
    assert f"secrets.{TOKEN_SECRET}" in flag
    assert "!= ''" in flag, "真偽値ではなく PAT の値そのものを env に載せている"


def test_warn_step_precedes_pr_creation(
    steps: list[dict[str, Any]],
    warn_step: dict[str, Any],
    create_pr_step: dict[str, Any],
) -> None:
    """警告ステップが PR 作成より前にあること。

    後ろに移ると本文への注記が PR に届かない。
    """
    assert steps.index(warn_step) < steps.index(create_pr_step)


def test_warn_step_runs_only_when_pat_is_missing(warn_step: dict[str, Any]) -> None:
    """警告ステップが「PAT 未設定のとき」だけ動く条件になっていること。

    条件が失われて常時実行になると、PAT が正しく設定されていても PR に警告が
    出続けて注記が形骸化する。
    """
    condition = warn_step["if"]
    assert HAS_TOKEN_ENV in condition, "未設定判定の env 参照が失われている"
    assert "'false'" in condition


def test_workflow_warns_when_pat_is_missing(warn_step: dict[str, Any]) -> None:
    """フォールバック時にジョブログへ警告を出すこと。

    静かに GITHUB_TOKEN へ落ちると #284 の症状（CI 未発火）に気づけないため。
    """
    assert "::warning::" in warn_step["run"], "PAT 未設定を知らせる警告が失われている"


def test_pr_body_is_annotated_when_pat_is_missing(
    warn_step: dict[str, Any], create_pr_step: dict[str, Any]
) -> None:
    """フォールバック時に PR 本文の冒頭へ注記を差し込んでいること。

    ジョブログの警告は自動実行では読まれないため、PR 本文側にも残す（#284）。
    """
    run = warn_step["run"]
    body_path = create_pr_step["with"]["body-path"]
    body_file = body_path.rsplit("/", 1)[-1]

    # 注記そのもの（警告の echo だけ残して注記を削る回帰を検出する）
    assert "[!WARNING]" in run, "PR 本文へ差し込む注記が失われている"
    # create-pull-request が読む本文ファイルを実際に書き換えていること。
    # `--summary-out` の指定とも一致する文字列なので、書き換え先の一時ファイルまで見る。
    assert body_file in run
    assert ".annotated." in run, "本文ファイルの書き換えが失われている"
