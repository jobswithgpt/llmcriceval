#!/usr/bin/env python3
import argparse, glob, json, os
import yaml

IGNORE_BOWLER_WK = {"run out", "retired hurt", "retired out", "obstructing the field"}

def load_yaml(fn):
    with open(fn, "r") as f:
        return yaml.safe_load(f)

def wicket_events(ball):
    w = ball.get("wicket")
    if not w:
        return []
    return w if isinstance(w, list) else [w]

def compute_team_totals(match):
    totals = {}
    for inn in match["innings"]:
        team = next(iter(inn.keys()))
        tot = 0
        for d in inn[team]["deliveries"]:
            ball = next(iter(d.values()))
            tot += ball["runs"]["total"]
        totals[team] = totals.get(team, 0) + tot
    return totals

def compute_runs_by_batter(match):
    runs = {}
    for inn in match["innings"]:
        team = next(iter(inn.keys()))
        for d in inn[team]["deliveries"]:
            b = next(iter(d.values()))
            runs[b["batsman"]] = runs.get(b["batsman"], 0) + b["runs"]["batsman"]
    return runs

def compute_wkts_by_bowler(match):
    wk = {}
    for inn in match["innings"]:
        team = next(iter(inn.keys()))
        for d in inn[team]["deliveries"]:
            b = next(iter(d.values()))
            for ev in wicket_events(b):
                kind = (ev.get("kind") or "").lower()
                if kind and kind not in IGNORE_BOWLER_WK:
                    wk[b["bowler"]] = wk.get(b["bowler"], 0) + 1
    return wk

def players_from_info_or_balls(match):
    players = set()
    info = match.get("info", {})
    plist = info.get("players")
    if isinstance(plist, dict):
        for arr in plist.values():
            for p in arr:
                players.add(p)
    if not players:
        for inn in match["innings"]:
            team = next(iter(inn.keys()))
            for d in inn[team]["deliveries"]:
                b = next(iter(d.values()))
                players.add(b["batsman"])
                players.add(b["bowler"])
                if "non_striker" in b:
                    players.add(b["non_striker"])
    return sorted(players)

def add_choice(items, _id, _type, prompt, options, gold_set, source):
    if not options or not gold_set:
        return
    items.append({
        "id": _id,
        "type": _type,
        "mode": "choice",
        "prompt": prompt,
        "options": options,
        "gold_set": list(gold_set),
        "source": source
    })

def add_number(items, _id, _type, prompt, gold, source, meta=None):
    if gold is None:
        return
    obj = {
        "id": _id,
        "type": _type,
        "mode": "number",
        "prompt": prompt,
        "gold": int(gold),
        "source": source
    }
    if meta:
        obj["meta"] = meta
    items.append(obj)

def gen_from_file(fn):
    m = load_yaml(fn)
    info = m["info"]
    date = info["dates"][0]
    venue = info.get("venue", "")
    teams = info["teams"]
    items = []

    team_totals = compute_team_totals(m)
    runs_by_batter = compute_runs_by_batter(m)
    wkts_by_bowler = compute_wkts_by_bowler(m)
    player_options = players_from_info_or_balls(m)

    # build stable id suffix
    base = os.path.basename(fn)

    # toss_winner (choice: teams)
    toss = info.get("toss", {})
    if "winner" in toss:
        add_choice(
            items,
            f"{base}#toss_winner",
            "toss_winner",
            f"Who won the toss in the T20 match between {teams[0]} and {teams[1]} on {date} at {venue}?",
            teams,
            [toss["winner"]],
            fn
        )

    # toss_decision (choice: bat/field)
    if "decision" in toss:
        add_choice(
            items,
            f"{base}#toss_decision",
            "toss_decision",
            f"What was the toss decision in the T20 match between {teams[0]} and {teams[1]} on {date} at {venue}?",
            ["bat", "field"],
            [toss["decision"]],
            fn
        )

    # match_winner (choice: teams)
    outcome = info.get("outcome", {})
    if "winner" in outcome:
        add_choice(
            items,
            f"{base}#match_winner",
            "match_winner",
            f"Who won the match between {teams[0]} and {teams[1]} on {date} at {venue}?",
            teams,
            [outcome["winner"]],
            fn
        )

    # victory_margin_runs (number)
    by = outcome.get("by", {})
    if "runs" in by:
        add_number(
            items,
            f"{base}#victory_margin_runs",
            "victory_margin_runs",
            f"By how many runs was the match between {teams[0]} and {teams[1]} on {date} at {venue} won?",
            by["runs"],
            fn
        )

    # victory_margin_wkts (number)
    if "wickets" in by:
        add_number(
            items,
            f"{base}#victory_margin_wkts",
            "victory_margin_wkts",
            f"By how many wickets was the match between {teams[0]} and {teams[1]} on {date} at {venue} won?",
            by["wickets"],
            fn
        )

    # team_total (number per team)
    for t, tot in team_totals.items():
        add_number(
            items,
            f"{base}#team_total:{t}",
            "team_total",
            f"How many runs did {t} score in the match on {date} at {venue}?",
            tot,
            fn,
            meta={"team": t}
        )

    # top_scorer_name (choice: players, ties allowed via gold_set)
    if runs_by_batter:
        top_runs = max(runs_by_batter.values())
        gold_set = sorted([p for p, r in runs_by_batter.items() if r == top_runs])
        add_choice(
            items,
            f"{base}#top_scorer_name",
            "top_scorer_name",
            f"Who scored the most runs in the match between {teams[0]} and {teams[1]} on {date} at {venue}?",
            player_options,
            gold_set,
            fn
        )
        # top_scorer_runs (number) for a deterministic player among ties
        pick = gold_set[0]
        add_number(
            items,
            f"{base}#top_scorer_runs:{pick}",
            "top_scorer_runs",
            f"How many runs did {pick} score in the match between {teams[0]} and {teams[1]} on {date} at {venue}?",
            runs_by_batter[pick],
            fn,
            meta={"player": pick}
        )

    # top_wicket_taker_name (choice: players, ties allowed)
    if wkts_by_bowler:
        top_wkts = max(wkts_by_bowler.values())
        gold_set = sorted([p for p, w in wkts_by_bowler.items() if w == top_wkts])
        add_choice(
            items,
            f"{base}#top_wicket_taker_name",
            "top_wicket_taker_name",
            f"Who took the most wickets in the match between {teams[0]} and {teams[1]} on {date} at {venue}?",
            player_options,
            gold_set,
            fn
        )
        pick = gold_set[0]
        add_number(
            items,
            f"{base}#top_wicket_taker_wickets:{pick}",
            "top_wicket_taker_wickets",
            f"How many wickets did {pick} take in the match between {teams[0]} and {teams[1]} on {date} at {venue}?",
            wkts_by_bowler[pick],
            fn,
            meta={"player": pick}
        )

    # total_match_runs (number)
    if team_totals:
        add_number(
            items,
            f"{base}#total_match_runs",
            "total_match_runs",
            f"What was the total runs scored in the match between {teams[0]} and {teams[1]} on {date} at {venue} (both teams combined)?",
            sum(team_totals.values()),
            fn
        )

    return items

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in_dir", default="t20_yaml")
    ap.add_argument("--out", default="t20_qa_all.jsonl")
    args = ap.parse_args()

    files = glob.glob(os.path.join(args.in_dir, "*.yaml"))
    total = 0
    with open(args.out, "w") as out:
        for fn in files:
            try:
                for item in gen_from_file(fn):
                    out.write(json.dumps(item, ensure_ascii=True) + "\n")
                    total += 1
            except Exception:
                continue
    print(f"wrote {total} QA to {args.out}")

if __name__ == "__main__":
    main()

