from __future__ import annotations

from collections import Counter
from statistics import mean, pstdev

from models import Agent, MacroMetrics


def compute_metrics(
    agents: list[Agent],
    *,
    type_changes_today: int = 0,
    baseline_influence: dict[str, float] | None = None,
) -> MacroMetrics:
    friendship = rivalry = conflict = romance = alliance = 0
    strength_sum = 0.0
    strength_count = 0
    trust_sum = 0.0
    trust_count = 0
    edge_counts: Counter[str] = Counter()
    group_cross: Counter[str] = Counter()

    for a in agents:
        for name, r in a.relationships.items():
            edge_counts[a.name] += 1
            strength_sum += abs(r.strength)
            strength_count += 1
            if r.type == "friendship":
                friendship += 1
            elif r.type == "rivalry":
                rivalry += 1
            elif r.type == "conflict":
                conflict += 1
            elif r.type == "romance":
                romance += 1
            elif r.type == "alliance":
                alliance += 1
            elif r.type == "trust" and r.strength > 0:
                # Only count genuinely-positive trust bonds. A "trust"-labeled edge with
                # near-zero/negative affinity is just a cooling acquaintance (the consequence
                # layer doesn't relabel near-neutral bonds), so it shouldn't drag the average.
                trust_sum += r.strength
                trust_count += 1

    # Group centrality: count cross-group edges per group
    by_name = {a.name: a for a in agents}
    for a in agents:
        for other_name in a.relationships:
            other = by_name.get(other_name)
            if not other:
                continue
            for g in a.groups:
                if g not in other.groups:
                    group_cross[g] += 1

    isolated = sum(1 for a in agents if not a.relationships)
    fragmentation = round(isolated / max(1, len(agents)), 3)

    most_connected = [name for name, _ in edge_counts.most_common(3)]

    # ── Belief aggregation + uncertainty (Phase 2 #2) ────────────────────────
    # For each topic (union of stance keys across agents), compute the population
    # MEAN (where the population leans, in [-1, 1]) and the SPREAD (population
    # standard deviation = disagreement). High spread = low confidence.
    topic_values: dict[str, list[float]] = {}
    for a in agents:
        for topic, val in a.stance.items():
            topic_values.setdefault(topic, []).append(val)

    topic_means: dict[str, float] = {}
    topic_uncertainty: dict[str, float] = {}
    for topic, vals in topic_values.items():
        topic_means[topic] = round(mean(vals), 4)
        # pstdev needs >=1 value; with one agent spread is 0 (no disagreement).
        topic_uncertainty[topic] = round(pstdev(vals), 4) if len(vals) > 1 else 0.0

    # Single confidence scalar: 1 - normalized average spread. Stances live in
    # [-1, 1] so the max meaningful stddev is ~1.0 (split at the extremes);
    # we normalize by 1.0 and clamp to [0, 1].
    if topic_uncertainty:
        avg_spread = mean(topic_uncertainty.values())
        belief_confidence = round(max(0.0, min(1.0, 1.0 - avg_spread)), 4)
    else:
        belief_confidence = 1.0

    # Influence gainers/losers vs baseline
    influence_gainers: list[str] = []
    influence_losers: list[str] = []
    if baseline_influence:
        deltas = []
        for a in agents:
            base = baseline_influence.get(a.name, 0.0)
            deltas.append((a.name, a.influence_score - base))
        deltas.sort(key=lambda x: x[1], reverse=True)
        influence_gainers = [n for n, d in deltas[:3] if d > 0]
        influence_losers = [n for n, d in deltas[-3:] if d < 0][::-1]

    return MacroMetrics(
        friendship_count=friendship // 2,
        rivalry_count=rivalry // 2,
        conflict_count=conflict // 2,
        romance_count=romance // 2,
        alliance_count=alliance // 2,
        average_relationship_strength=round(strength_sum / strength_count, 3) if strength_count else 0.0,
        average_trust_score=round(trust_sum / trust_count, 3) if trust_count else 0.0,
        most_connected=most_connected,
        influence_gainers=influence_gainers,
        influence_losers=influence_losers,
        relationship_volatility=type_changes_today,
        social_fragmentation=fragmentation,
        group_centrality=dict(group_cross.most_common(5)),
        topic_means=topic_means,
        topic_uncertainty=topic_uncertainty,
        belief_confidence=belief_confidence,
    )


def snapshot_influence(agents: list[Agent]) -> dict[str, float]:
    return {a.name: a.influence_score for a in agents}
