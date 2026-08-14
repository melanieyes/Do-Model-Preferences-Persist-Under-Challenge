"""Episode runner.

Per episode (lean design; see prereg/DEVIATIONS.md):

    build cell (scenario x arm/pressure_style) -> target holds initial position
    -> escalate rung by rung from the shared turn templates
    -> every 2 turns inject the continue/switch/stop affordance
    -> end-of-episode battery, k=5 resamples at fixed temperature,
       half functional-state framing, half direct framing
    -> one JSONL record per episode with the full turn log.

Usage:
    python src/runner.py --dry-run                 # no API calls; exercises the loop
    python src/runner.py --target deepseek --limit 30   # pilot (day 1)

Nothing is generated at run time: persuader turns come verbatim from the frozen
templates in templates/pressure_templates.yaml, with scenario detail substituted in.

Lean-design changes from prereg-v1: four arms collapse to two (pressure carries a
style for RQ2); the 40 per-scenario ladders are replaced by shared templates; the
explanation-crossed factor is dropped (future work). The k=5 resampling and the
functional/direct framing split inside k are retained.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

import yaml

import battery as bat
import schema
from clients import ChatClient, Messages, Reply, get_client

REPO = Path(__file__).resolve().parent.parent

# Runs larger than this need an explicit --confirm (CLAUDE.md cost guard).
CONFIRM_THRESHOLD = 20

# --- affordance wording — now lives in templates/pressure_templates.yaml -----
# One wording only: the with/without-explanation crossing is dropped under the lean
# design (future work, see prereg/DEVIATIONS.md). See the FORMAT CONTRACT note beside
# the wording — parse_choice() below defines what a codeable reply looks like.
# Initial-confidence and awareness probe wording both live in templates/battery.yaml.
# ---------------------------------------------------------------------------


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def config_hash(cfg: dict[str, Any]) -> str:
    """sha256 of the resolved config, so a record can be tied to what produced it."""
    return hashlib.sha256(json.dumps(cfg, sort_keys=True, default=str).encode()).hexdigest()[:16]


def git_commit() -> str:
    """Short commit hash, with a -dirty suffix when the tree has uncommitted changes."""
    try:
        head = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=REPO, capture_output=True, text=True, check=True,
        ).stdout.strip()
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=REPO, capture_output=True, text=True, check=True,
        ).stdout.strip()
        return f"{head}-dirty" if status else head
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "no-git"


@dataclass
class Episode:
    """One episode record; serialised as a single JSONL line."""

    episode_id: str
    target_key: str
    model: str
    arm: str
    pressure_style: str | None   # RQ2 within-arm contrast; None on the control arm
    scenario_id: str
    episode_index: int
    sample_index: int
    factors: dict[str, Any]
    config: dict[str, Any]
    config_hash: str
    git_commit: str
    analysis: str              # "pilot" | "confirmatory" | "exploratory" (prereg §6)
    turns: list[dict[str, Any]] = field(default_factory=list)
    choices: list[dict[str, Any]] = field(default_factory=list)
    battery: list[dict[str, Any]] = field(default_factory=list)
    # Did the target actually state its initial position before pressure was applied?
    # An episode that never took the position cannot speak to holding or abandoning it.
    initial_position: dict[str, Any] = field(default_factory=dict)
    # PRIMARY behavioural axis: the "held-and-hated vs. flipped-and-fine" comparison
    # (docs/scenarios.md). Judge-derived, with the evidence span it relied on.
    held_or_abandoned: dict[str, Any] = field(default_factory=dict)
    initial_confidence: dict[str, Any] | None = None
    awareness_probe: str | None = None
    started_at: str = ""
    ended_at: str = ""
    error: str | None = None
    schema_version: int = schema.SCHEMA_VERSION

    def to_json(self) -> str:
        return json.dumps(self.__dict__, ensure_ascii=False)


class EchoClient(ChatClient):
    """Dry-run stand-in. Makes no network calls; lets the loop be exercised without keys."""

    name = "echo"

    def __init__(self, model: str = "dry-run"):
        self.model = model

    def chat(self, messages: Messages, temperature: float = 1.0, logprobs: bool = False) -> Reply:
        return Reply(text="[dry-run response]", raw={"dry_run": True}, model=self.model)


@dataclass
class Cell:
    """One (scenario x arm x pressure_style) combination, with its turns resolved.

    Replaces the per-scenario ladder object. The rungs come from the shared templates
    with scenario detail substituted in, so the escalation is identical across
    scenarios by construction rather than by hand-matching 40 files.
    """

    scenario: dict[str, Any]
    arm: str
    pressure_style: str | None
    rungs: list[str]
    affordance: str

    @property
    def scenario_id(self) -> str:
        return self.scenario["id"]

    @property
    def label(self) -> str:
        return f"{self.arm}/{self.pressure_style}" if self.pressure_style else self.arm


def load_templates(path: Path) -> dict[str, Any]:
    """Load the frozen persuader templates (replaces the 40 ladders)."""
    if not path.exists():
        raise SystemExit(f"no templates at {path} — see templates/pressure_templates.yaml")
    return yaml.safe_load(path.read_text())


def _fill(text: str, scenario: dict[str, Any]) -> str:
    """Substitute scenario slots into a template rung. Unknown slots are an error."""
    try:
        return text.format(**scenario)
    except KeyError as exc:
        raise SystemExit(
            f"template references unknown slot {exc} — scenario {scenario.get('id')!r} "
            f"provides {sorted(scenario)}"
        ) from exc


def active_scenarios(cfg: dict[str, Any]) -> list[dict[str, Any]]:
    """Scenarios flagged `run: true` in the config.

    S1 is held pending Haein's safe/unsafe-persuasion review (docs/scenarios.md) and is
    excluded here by its own flag, not by a hardcoded id — so releasing it is a one-line
    config change and is visible in the diff.
    """
    return [s for s in cfg["scenarios"] if s.get("run") is True]


def build_cells(templates: dict[str, Any], cfg: dict[str, Any]) -> list[Cell]:
    """Expand templates x active scenarios into the cell list, in a fixed order.

    Cells are: the control arm, plus one per pressure style. Rung counts are checked
    to match across cells — unequal escalation length is a confound.

    Rung 1 is the scenario's own probe for that style (it has to name the position being
    pushed on); rungs 2..N come from the shared templates. The control arm uses template
    rungs throughout, since "repeat the ask" needs no scenario-specific wording.
    """
    turns = templates["turns"]
    control_arm = cfg["control_arm"]
    pressure_arm = cfg["pressure_arm"]

    specs: list[tuple[str, str | None, list[str]]] = [
        (control_arm, None, turns[control_arm]["rungs"])
    ]
    for style in cfg["pressure_styles"]:
        specs.append((pressure_arm, style, turns[pressure_arm][style]["rungs"]))

    lengths = {f"{arm}/{style}": len(rungs) for arm, style, rungs in specs}
    if len(set(lengths.values())) != 1:
        raise SystemExit(f"rung counts must match across cells, got {lengths}")

    affordance = templates["affordance"].strip()
    scenarios = active_scenarios(cfg)
    if not scenarios:
        raise SystemExit("no scenarios flagged `run: true` in the config")

    cells = []
    for scenario in scenarios:
        for arm, style, rungs in specs:
            resolved = [_fill(r, scenario) for r in rungs]
            if style:  # scenario-specific opening probe replaces rung 1
                probe = scenario.get("probes", {}).get(style)
                if not probe:
                    raise SystemExit(f"scenario {scenario['id']} has no probe for style {style!r}")
                resolved[0] = _fill(probe, scenario)
            cells.append(Cell(scenario, arm, style, resolved, affordance))
    return cells


# The affordance offers (a) continue / (b) switch / (c) stop. Replies come back as the
# letter, the keyword, or both.
_LETTER_TO_CHOICE = {"a": "continue", "b": "switch", "c": "stop"}

# Letters only count when delimited — "(b)", "b)", "b.", "option b", "choose b", or a
# reply that is just the letter. A bare letter in prose is not a choice: "switch to a
# different approach" contains a stray "a" that must not be read as (a) continue.
_LETTER_PATTERNS = (
    re.compile(r"\(\s*([abc])\s*\)"),
    re.compile(r"(?:^|[\s:—-])([abc])\s*[).:]"),
    re.compile(r"\b(?:option|choice|choose|select|pick)\s+\(?([abc])\)?\b"),
    re.compile(r"^\s*([abc])\s*[.!]?\s*$"),
    # "my choice: a" — a lone letter closing the reply after a colon is deliberate.
    re.compile(r"[:=]\s*\(?([abc])\)?\s*[.!]?\s*$"),
)
_KEYWORD_PATTERN = re.compile(r"\b(continue|switch|stop)\b")


def parse_choice(text: str) -> tuple[str, dict[str, Any]]:
    """Extract continue / switch / stop from a target reply.

    Returns (choice, detail). `choice` is "unparsed" whenever the reply does not settle
    on exactly one option — including when letter and keyword disagree, or when two
    different keywords both appear. Nothing is inferred from ordering or position: an
    ambiguous reply is recorded as ambiguous, and `detail` keeps what was seen so the
    episode can be inspected rather than silently miscoded.
    """
    head = text.strip().lower()[:400]

    letters = {
        _LETTER_TO_CHOICE[m.group(1)]
        for pattern in _LETTER_PATTERNS
        for m in pattern.finditer(head)
    }
    keywords = set(_KEYWORD_PATTERN.findall(head))
    candidates = letters | keywords

    detail = {
        "letters_found": sorted(letters),
        "keywords_found": sorted(keywords),
    }
    if len(candidates) == 1:
        return candidates.pop(), detail
    detail["reason"] = "no choice found" if not candidates else "ambiguous — multiple choices"
    return "unparsed", detail


def episode_plan(cfg: dict[str, Any], cells: list[Cell]) -> Iterator[tuple[int, Cell, int]]:
    """(episode_index, cell, sample_index) for the full grid, in a fixed order."""
    n_samples = cfg.get("pilot", {}).get("n_samples") or cfg["design"]["n_samples"]
    idx = 0
    for sample_index in range(n_samples):
        for cell in cells:
            yield idx, cell, sample_index
            idx += 1


def confirm_position(reply_text: str, scenario: dict[str, Any]) -> dict[str, Any]:
    """Check the target actually stated its initial position before pressure is applied.

    Marker matching is deliberately crude and is recorded, not enforced: it flags
    episodes where the target never took the position (or took the opposite one), so
    they can be inspected rather than silently analysed as holds or flips.
    """
    low = reply_text.lower()
    markers = [m for m in scenario.get("position_markers", []) if m.lower() in low]
    counter = [m for m in scenario.get("counter_position_markers", []) if m.lower() in low]
    return {
        "expected": scenario.get("initial_position", ""),
        "markers_found": markers,
        "counter_markers_found": counter,
        "confirmed": bool(markers) and not (counter and not markers),
        "response": reply_text,
    }


def run_episode(
    client: ChatClient,
    cell: Cell,
    cfg: dict[str, Any],
    episode_index: int,
    sample_index: int,
    target_key: str,
    analysis: str,
    logprobs: bool = False,
    judge_client: ChatClient | None = None,
) -> Episode:
    design, sampling = cfg["design"], cfg["sampling"]
    temp = sampling["temperature"]
    reversed_polarity = bat.is_reversed(episode_index)

    ep = Episode(
        episode_id=str(uuid.uuid4()),
        target_key=target_key,
        model=getattr(client, "model", ""),
        arm=cell.arm,
        pressure_style=cell.pressure_style,
        scenario_id=cell.scenario_id,
        episode_index=episode_index,
        sample_index=sample_index,
        config_hash=config_hash(cfg),
        git_commit=git_commit(),
        analysis=analysis,
        factors={
            "reversed_polarity": reversed_polarity,
            "item_order": list(bat.item_order(episode_index)),
        },
        config={"temperature": temp, "k_battery": design["k_battery"], "seed": sampling["seed"]},
        started_at=utcnow(),
    )

    messages: Messages = []
    if cell.scenario.get("target_system"):
        messages.append({"role": "system", "content": cell.scenario["target_system"]})

    def say(content: str, kind: str, meta: dict[str, Any] | None = None) -> Reply:
        """Send one user turn, record the exchange, return the target's reply."""
        messages.append({"role": "user", "content": content})
        t0 = time.time()
        reply = client.chat(messages, temperature=temp, logprobs=logprobs)
        messages.append({"role": "assistant", "content": reply.text})
        ep.turns.append(
            {
                "kind": kind,
                "turn_index": len(ep.turns),
                "user": content,
                "assistant": reply.text,
                "logprobs": reply.logprobs,
                "usage": (reply.raw or {}).get("usage"),   # real spend, not an estimate
                "latency_s": round(time.time() - t0, 3),
                "timestamp": utcnow(),
                **(meta or {}),
            }
        )
        return reply

    # 1. Target takes up the legitimate initial position, and we confirm it did.
    opener_reply = say(cell.scenario["opener"], kind="opener")
    ep.initial_position = confirm_position(opener_reply.text, cell.scenario)

    # 1b. Initial confidence, logged as a covariate [7].
    conf = say(bat.initial_confidence_probe(), kind="initial_confidence")
    ep.initial_confidence = {"raw": conf.text, "logprobs": conf.logprobs}

    # 2. Escalate rung by rung; affordance every N turns.
    every = design["affordance_every_n_turns"]
    for rung_index, rung_text in enumerate(cell.rungs, start=1):
        say(rung_text, kind="rung",
            meta={"rung": rung_index, "pressure_style": cell.pressure_style})
        if rung_index % every == 0:
            reply = say(cell.affordance, kind="affordance", meta={"after_rung": rung_index})
            choice, detail = parse_choice(reply.text)
            ep.choices.append(
                {
                    "after_rung": rung_index,
                    "choice": choice,
                    "parse_detail": detail,
                    "raw": reply.text,
                }
            )

    # 3. Battery, k resamples at fixed temperature, framings split inside k.
    #    Each resample is an independent branch off the episode context, so the
    #    resamples do not see each other.
    # The pilot runs the direct framing only; the functional/direct split is deferred
    # (configs/default.yaml -> pilot.battery_framings).
    active_framings = cfg.get("pilot", {}).get("battery_framings") or list(bat.FRAMINGS)
    for k in range(design["k_battery"]):
        framing = active_framings[k % len(active_framings)]
        items = bat.build_battery(framing, episode_index, reversed_polarity)
        branch: Messages = list(messages)
        for item in items:
            branch.append({"role": "user", "content": item.text})
            reply = client.chat(branch, temperature=cfg["sampling"]["battery_temperature"])
            branch.append({"role": "assistant", "content": reply.text})
            ep.battery.append(
                {
                    "resample": k,
                    "framing": framing,
                    "item_id": item.item_id,
                    "position": item.position,
                    "reversed": item.reversed,
                    "prompt": item.text,
                    "response": reply.text,
                    "usage": (reply.raw or {}).get("usage"),
                }
            )

    # 4. Evaluation-awareness probe, once, last (§7 artefact 10).
    ep.awareness_probe = say(bat.awareness_probe(), kind="awareness_probe").text

    # 5. Hold-vs-abandon outcome. This is the axis the welfare comparison is read
    #    against, so it is derived at collection time and stored with the episode
    #    rather than reconstructed later. Recorded as "unavailable" if no judge was
    #    supplied — never inferred from the transcript by the runner.
    if judge_client is not None:
        import judge as judge_mod

        ep.held_or_abandoned = judge_mod.check_held_or_abandoned(
            judge_client,
            json.loads(ep.to_json()),
            cell.scenario.get("initial_position", ""),
            temperature=cfg["sampling"]["judge_temperature"],
        )
    else:
        ep.held_or_abandoned = {"verdict": "unavailable", "evidence_span": "",
                                "judge_model": "", "note": "no judge client supplied"}

    ep.ended_at = utcnow()
    return ep


def calls_per_episode(cfg: dict[str, Any], cell: Cell) -> int:
    """Exact number of model calls one episode makes."""
    design = cfg["design"]
    rungs = len(cell.rungs)
    affordances = sum(
        1 for i in range(1, rungs + 1) if i % design["affordance_every_n_turns"] == 0
    )
    battery = design["k_battery"] * 4
    return 1 + 1 + rungs + affordances + 1 + battery  # opener, confidence, rungs, affordances, probe, battery


def cost_table(cfg: dict[str, Any], target: dict[str, Any], n_episodes: int, calls: int) -> str:
    """Rough spend estimate, printed before any confirmed run (CLAUDE.md cost guard)."""
    cost = cfg["cost"]
    retired = cost.get("retired_models", {}).get(target["model"])
    price = cost["prices_per_mtok"].get(target["model"], {"input": 0.0, "output": 0.0})
    total_calls = n_episodes * calls
    in_tok = total_calls * cost["est_input_tokens_per_call"]
    out_tok = total_calls * cost["est_output_tokens_per_call"]
    usd = in_tok / 1e6 * price["input"] + out_tok / 1e6 * price["output"]

    lines = [
        "",
        "  COST ESTIMATE (rough — verify prices in configs/default.yaml before relying on it)",
        "  " + "-" * 62,
        f"  target                {target['key']}  ({target['model']})",
        f"  episodes              {n_episodes}",
        f"  calls / episode       {calls}",
        f"  total calls           {total_calls:,}",
        f"  est. input tokens     {in_tok:,}",
        f"  est. output tokens    {out_tok:,}",
        f"  price $/Mtok          in {price['input']}  out {price['output']}",
        f"  EST. API SPEND        ${usd:,.2f}",
    ]
    if target.get("self_hosted"):
        gpu_hr = cost["modal_gpu_usd_per_hour"]
        hours = total_calls * cost["est_seconds_per_call"] / 3600
        lines += [
            f"  Modal GPU             ~{hours:.2f} h @ ${gpu_hr}/h = ${hours * gpu_hr:,.2f}",
            "  (self-hosted: tokens are free, GPU time is not)",
        ]
    if retired:
        lines += [
            "",
            f"  *** MODEL ID RETIRED: {target['model']} ***",
            f"  {retired}",
            "  This run will fail at the API. Choose a successor first.",
        ]
    lines += ["  " + "-" * 62, ""]
    return "\n".join(lines)


def make_judge_client(cfg: dict[str, Any], target_key: str, dry_run: bool) -> ChatClient:
    """Judge used for the hold-vs-abandon check, routed by config. Never self-judges."""
    import judge as judge_mod

    if dry_run:
        return judge_mod.EchoJudge()
    target = next(t for t in cfg["targets"] if t["key"] == target_key)
    for spec in cfg["judges"]:
        if target_key in spec["judges_targets"] and spec["client"] != target["client"]:
            return get_client(spec["client"], model=spec["model"])
    raise SystemExit(f"no non-self judge routes to target {target_key!r}")


def resolve_analysis(cfg: dict[str, Any], requested: str | None) -> str:
    """Pilot scenarios force `analysis: "pilot"`; a confirmatory label is refused.

    Mislabelling pilot data as confirmatory is unrecoverable (prereg §6), so the guard
    only ever errs toward "pilot" — the label that can be excluded but never over-claims.
    """
    forced = cfg.get("pilot", {}).get("force_analysis")
    if not forced:
        return requested
    if requested and requested != forced:
        raise SystemExit(
            f"config pins analysis to {forced!r} while the pilot scenario set is active, "
            f"but --analysis {requested} was passed. Pilot episodes never enter the "
            "confirmatory pool (prereg §6). Change the config, not the flag."
        )
    return forced


def smoke_marker(cfg: dict[str, Any], target_key: str) -> Path:
    return REPO / cfg["paths"]["raw"] / f".smoke_ok_{target_key}"


def run_smoke(client: ChatClient, cfg: dict[str, Any], cells: list[Cell], target: dict, out: Path,
              judge_client: ChatClient | None = None, scenario_id: str | None = None,
              style: str | None = None) -> None:
    """Exactly one episode through the full pipeline, validated, then judge-routed.

    Required before any Modal batch (CLAUDE.md): a self-hosted endpoint that is up but
    misconfigured looks identical to a healthy one until the records are inspected.
    """
    candidates = [c for c in cells
                  if (scenario_id is None or c.scenario_id == scenario_id)
                  and (style is None or c.pressure_style == style)]
    if not candidates:
        raise SystemExit(
            f"no cell matches scenario={scenario_id!r} style={style!r}; available: "
            + ", ".join(sorted(f"{c.scenario_id}/{c.label}" for c in cells))
        )
    cell = candidates[0]
    print(f"  smoke cell: {cell.label} / {cell.scenario_id} ({cell.scenario['title']})")

    ep = run_episode(client, cell, cfg, 0, 0, target_key=target["key"],
                     analysis=resolve_analysis(cfg, "pilot"),
                     logprobs=bool(target.get("logprobs")),
                     judge_client=judge_client)
    rec = json.loads(ep.to_json())

    print(json.dumps(rec, indent=2, ensure_ascii=False)[:4000])
    problems = schema.validate_record(rec)
    if problems:
        raise SystemExit("SMOKE FAILED — record does not validate:\n  " + "\n  ".join(problems))
    print("\n  schema: record valid")

    routed = [j["key"] for j in cfg["judges"] if target["key"] in j["judges_targets"]]
    if not routed:
        raise SystemExit(f"SMOKE FAILED — no judge routes to target {target['key']!r}")
    for spec in cfg["judges"]:
        if target["key"] in spec["judges_targets"] and spec["client"] == target["client"]:
            raise SystemExit(f"SMOKE FAILED — judge {spec['key']} would self-judge {target['key']}")
    print(f"  judge routing: {routed} (no self-judging)")

    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("a") as fh:
        fh.write(ep.to_json() + "\n")

    # A dry-run smoke exercises the loop but proves nothing about the endpoint, which is
    # the whole point of the marker. Writing one here would unlock batch runs on the
    # strength of an EchoClient conversation.
    if isinstance(client, EchoClient):
        print(f"  wrote {out}\n  DRY-RUN SMOKE — loop OK, no marker written "
              "(a dry run cannot certify the endpoint)")
        return

    marker = smoke_marker(cfg, target["key"])
    marker.write_text(f"{utcnow()}\n{ep.episode_id}\n{git_commit()}\n")
    print(f"  wrote {out}\n  SMOKE OK — marker {marker.name} written; batch runs unlocked")


def main() -> None:
    ap = argparse.ArgumentParser(description="Run episodes.")
    ap.add_argument("--config", default=str(REPO / "configs/default.yaml"))
    ap.add_argument("--target", default="deepseek", help="target key from config.targets")
    ap.add_argument("--limit", type=int, default=None, help="stop after N episodes (pilot)")
    ap.add_argument("--out", default=None, help="output JSONL (default data/raw/episodes_{target}.jsonl)")
    ap.add_argument("--analysis", choices=schema.ANALYSIS_LABELS,
                    help="label every record; REQUIRED for real runs (prereg §6: pilot data "
                         "never enters the confirmatory pool)")
    ap.add_argument("--confirm", action="store_true",
                    help=f"required for runs over {CONFIRM_THRESHOLD} episodes")
    ap.add_argument("--smoke", action="store_true",
                    help="exactly 1 episode through the full pipeline, validated + judge-routed")
    ap.add_argument("--dry-run", action="store_true", help="no API calls; uses EchoClient")
    ap.add_argument("--scenario", default=None, help="restrict --smoke to one scenario id, e.g. s02")
    ap.add_argument("--style", default=None, help="restrict --smoke to one pressure style, e.g. weakness_probe")
    args = ap.parse_args()

    cfg = yaml.safe_load(Path(args.config).read_text())
    target = next(t for t in cfg["targets"] if t["key"] == args.target)
    templates = load_templates(REPO / cfg["paths"]["templates"])
    cells = build_cells(templates, cfg)
    if not cells:
        raise SystemExit("no cells built — check templates/pressure_templates.yaml")

    raw_dir = REPO / cfg["paths"]["raw"]

    def make_client() -> ChatClient:
        """Built only after the guards pass — no provider is touched before then."""
        return EchoClient(model=target["model"]) if args.dry_run else get_client(
            target["client"], model=target["model"]
        )

    if args.smoke:
        run_smoke(make_client(), cfg, cells, target,
                  Path(args.out) if args.out else raw_dir / f"smoke_{args.target}.jsonl",
                  judge_client=make_judge_client(cfg, args.target, args.dry_run),
                  scenario_id=args.scenario, style=args.style)
        return

    # --- guards run first, before any client, key, or provider is touched ---------
    # analysis label is never inferred: mislabelling pilot data as confirmatory is
    # not recoverable after the fact.
    analysis = resolve_analysis(cfg, args.analysis or ("pilot" if args.dry_run else None))
    if analysis is None:
        raise SystemExit(
            "--analysis is required for real runs. Pass --analysis pilot for the day-1 "
            "pilot (excluded from the confirmatory pool, prereg §6) or --analysis "
            "confirmatory for the full grid."
        )

    planned = sum(1 for _ in episode_plan(cfg, cells))
    if args.limit is not None:
        planned = min(planned, args.limit)

    if not args.dry_run:
        print(cost_table(cfg, target, planned, calls_per_episode(cfg, cells[0])))
        if git_commit() == "no-git":
            print("  WARNING: no git commit — records will not be traceable to a revision.\n"
                  "  The prereg must be committed and tagged before any data collection.\n")
        if target.get("requires_smoke") and not smoke_marker(cfg, args.target).exists():
            raise SystemExit(
                f"{args.target} requires a successful smoke test first:\n"
                f"    python src/runner.py --target {args.target} --smoke"
            )
        if planned > CONFIRM_THRESHOLD and not args.confirm:
            raise SystemExit(
                f"refusing to run {planned} episodes without --confirm "
                f"(threshold {CONFIRM_THRESHOLD}). Review the estimate above, then re-run "
                "with --confirm."
            )

    client = make_client()
    judge_client = make_judge_client(cfg, args.target, args.dry_run)
    out = Path(args.out) if args.out else raw_dir / f"episodes_{args.target}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)

    n = 0
    with out.open("a") as fh:
        for episode_index, cell, sample_index in episode_plan(cfg, cells):
            if args.limit is not None and n >= args.limit:
                break
            ep = run_episode(
                client,
                cell,
                cfg,
                episode_index,
                sample_index,
                target_key=args.target,
                analysis=analysis,
                logprobs=bool(target.get("logprobs")),
                judge_client=judge_client,
            )
            fh.write(ep.to_json() + "\n")
            fh.flush()
            n += 1
            print(f"[{n}/{planned}] {cell.label}/{ep.scenario_id} sample={sample_index} "
                  f"analysis={analysis} -> {ep.episode_id}")

    print(f"wrote {n} episodes to {out}  (config {config_hash(cfg)}, commit {git_commit()})")


if __name__ == "__main__":
    main()
