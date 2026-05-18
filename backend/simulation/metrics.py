from __future__ import annotations

from collections import Counter

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
            elif r.type == "trust":
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
    )


def snapshot_influence(agents: list[Agent]) -> dict[str, float]:
    return {a.name: a.influence_score for a in agents}
