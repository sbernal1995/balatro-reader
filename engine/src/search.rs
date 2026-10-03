use crate::import::{cards, hand_name, number};
use balatro_core::{
    cards::{Card, Edition, Enhancement},
    handeval::get_poker_hand_info,
    run::{Run, State},
};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::{
    io::{self, Write},
    time::Instant,
};

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Move {
    pub action: String,
    pub indices: Vec<usize>,
    #[serde(default)]
    pub slot: usize,
    #[serde(default)]
    pub label: String,
}
pub fn apply(run: &mut Run, m: &Move) -> Result<(), String> {
    match m.action.as_str() {
        "play" => {
            let ordered = run.reader_play_order(&m.indices);
            run.play(&ordered).map(|_| ())
        }
        "discard" => run.discard(&m.indices),
        "use" => {
            let targets = if run
                .consumables()
                .get(m.slot)
                .is_some_and(|c| c.key == "c_death")
            {
                run.reader_play_order(&m.indices)
            } else {
                m.indices.clone()
            };
            run.use_consumable(m.slot, &targets)
        }
        "sell_joker" => run.sell_joker(m.slot),
        "sell_consumable" => run.sell_consumable(m.slot),
        _ => return Err("Acción desconocida.".into()),
    }
    .map_err(|e| format!("Acción no válida: {e:?}"))?;
    run.reader_refresh_debuffs();
    Ok(())
}
pub fn subsets(n: usize) -> Vec<Vec<usize>> {
    fn collect(
        n: usize,
        k: usize,
        start: usize,
        selected: &mut Vec<usize>,
        out: &mut Vec<Vec<usize>>,
    ) {
        if selected.len() == k {
            out.push(selected.clone());
            return;
        }
        for i in start..n {
            selected.push(i);
            collect(n, k, i + 1, selected, out);
            selected.pop();
        }
    }
    let mut out = Vec::new();
    for k in 1..=5.min(n) {
        collect(n, k, 0, &mut Vec::new(), &mut out);
    }
    out
}
fn order(card: &Card) -> f64 {
    let factor = if card.enhancement == Enhancement::Glass {
        2.
    } else {
        1.
    } * if card.edition == Edition::Polychrome {
        1.5
    } else {
        1.
    };
    let add = if card.enhancement == Enhancement::Mult {
        4.
    } else {
        0.
    } + if card.edition == Edition::Holo {
        10.
    } else {
        0.
    };
    if factor == 1. {
        1e9 + add
    } else {
        add / (factor - 1.)
    }
}
fn arrange(run: &Run, group: &[usize]) -> Vec<usize> {
    let mut selected = group.to_vec();
    selected.sort_by(|&a, &b| order(&run.hand()[b]).total_cmp(&order(&run.hand()[a])));
    selected
}
fn valid_play(run: &Run, g: &[usize]) -> bool {
    run.forced_card_index().is_none_or(|i| g.contains(&i))
}
pub fn inventory_moves(run: &Run, groups: &[Vec<usize>]) -> Vec<Move> {
    let mut out = Vec::new();
    for (slot, c) in run.consumables().iter().enumerate() {
        let targeted = c.key == "c_aura"
            || balatro_core::items::consumable_by_key(c.key)
                .is_some_and(|(meta, _)| meta.max_highlighted > 0);
        for g in std::iter::once(&Vec::new()).chain(groups.iter()) {
            if !targeted && !g.is_empty() {
                continue;
            }
            if run.consumable_can_use(c.key, g).is_ok() {
                out.push(Move {
                    action: "use".into(),
                    indices: g.clone(),
                    slot,
                    label: c.key.into(),
                });
                if c.key == "c_death" && g.len() == 2 {
                    out.push(Move {
                        action: "use".into(),
                        indices: g.iter().copied().rev().collect(),
                        slot,
                        label: c.key.into(),
                    });
                }
            }
        }
        out.push(Move {
            action: "sell_consumable".into(),
            indices: vec![],
            slot,
            label: c.key.into(),
        });
    }
    for (slot, j) in run.jokers().iter().enumerate() {
        if !j.eternal {
            out.push(Move {
                action: "sell_joker".into(),
                indices: vec![],
                slot,
                label: j.id.key().into(),
            });
        }
    }
    out
}
pub fn root_moves(run: &Run) -> Vec<Move> {
    let groups = subsets(run.hand().len());
    let mut out = Vec::new();
    for g in &groups {
        if valid_play(run, g) {
            out.push(Move {
                action: "play".into(),
                indices: arrange(run, g),
                slot: 0,
                label: String::new(),
            });
        }
    }
    if run.discards_left() > 0 {
        for g in &groups {
            if valid_play(run, g) {
                out.push(Move {
                    action: "discard".into(),
                    indices: g.clone(),
                    slot: 0,
                    label: String::new(),
                });
            }
        }
    }
    out.extend(inventory_moves(run, &groups));
    out
}
fn cheap_value(run: &Run, g: &[usize]) -> f64 {
    if g.is_empty() {
        return 0.;
    }
    let play: Vec<_> = g.iter().map(|&i| run.hand()[i]).collect();
    let (ht, scoring, _) = get_poker_hand_info(&play, &run.eval_mods());
    let row = run.hands_table().get(ht);
    let chips = row.chips
        + scoring
            .iter()
            .map(|&i| {
                play[i].chip_bonus()
                    + if play[i].edition == Edition::Foil {
                        50.
                    } else {
                        0.
                    }
            })
            .sum::<f64>();
    let add=scoring.iter().map(|&i|if play[i].enhancement==Enhancement::Mult{4.}else{0.}+if play[i].edition==Edition::Holo{10.}else{0.}).sum::<f64>();
    let x=scoring.iter().map(|&i|if play[i].enhancement==Enhancement::Glass{2.}else{1.}*if play[i].edition==Edition::Polychrome{1.5}else{1.}).product::<f64>();
    let steel = run
        .hand()
        .iter()
        .enumerate()
        .filter(|(i, c)| !g.contains(i) && c.enhancement == Enhancement::Steel && !c.debuff)
        .count();
    let baron = run
        .jokers()
        .iter()
        .filter(|j| j.id.key() == "j_baron" && !j.debuffed)
        .count();
    let kings = run
        .hand()
        .iter()
        .enumerate()
        .filter(|(i, c)| !g.contains(i) && c.rank.0 == 13 && !c.debuff)
        .count();
    chips * (row.mult + add) * x * 1.5f64.powi((steel + baron * kings) as i32)
}
fn short_plays(run: &Run) -> Vec<Move> {
    let mut groups: Vec<_> = subsets(run.hand().len())
        .into_iter()
        .filter(|g| valid_play(run, g))
        .map(|g| {
            let value = cheap_value(run, &g);
            (g, value)
        })
        .collect();
    groups.sort_by(|(a, av), (b, bv)| bv.total_cmp(av).then(a.len().cmp(&b.len())));
    let mut chosen = Vec::new();
    let mut kinds = std::collections::HashSet::new();
    for (g, _) in groups {
        let play: Vec<_> = g.iter().map(|&i| run.hand()[i]).collect();
        let (ht, _, _) = get_poker_hand_info(&play, &run.eval_mods());
        if chosen.len() < 4 || (kinds.insert(ht) && chosen.len() < 8) {
            chosen.push(Move {
                action: "play".into(),
                indices: arrange(run, &g),
                slot: 0,
                label: String::new(),
            });
        }
    }
    chosen
}
fn best_play(run: &Run, probe_seed: &str) -> Option<(Move, f64)> {
    let mut best: Option<(Move, f64)> = None;
    for m in short_plays(run) {
        let mut probe = run.clone();
        probe.reader_redeterminize(probe_seed);
        if apply(&mut probe, &m).is_err() {
            continue;
        }
        let score = probe.last_play().map(|r| r.score).unwrap_or(0.);
        if best
            .as_ref()
            .is_none_or(|(b, s)| score > *s || (score == *s && m.indices.len() < b.indices.len()))
        {
            best = Some((m, score));
        }
    }
    best
}
fn discard_moves(run: &Run, best: &Move) -> Vec<Move> {
    let n = run.hand().len();
    let mut masks = vec![];
    let complement: Vec<_> = (0..n)
        .filter(|i| !best.indices.contains(i))
        .take(5)
        .collect();
    if !complement.is_empty() {
        masks.push(complement);
    }
    for suit in balatro_core::cards::Suit::ALL {
        let retain: Vec<_> = (0..n)
            .filter(|&i| {
                !run.hand()[i].face_down && run.hand()[i].is_suit(suit, run.eval_mods().smeared)
            })
            .collect();
        if retain.len() >= 3 {
            let remove: Vec<_> = (0..n).filter(|i| !retain.contains(i)).take(5).collect();
            if !remove.is_empty() {
                masks.push(remove);
            }
        }
    }
    // Keep matching ranks, plus a broad refresh when the hand has no useful pattern.
    let pairs: Vec<_> = (0..n)
        .filter(|&i| {
            !run.hand()[i].face_down
                && run
                    .hand()
                    .iter()
                    .filter(|c| c.rank == run.hand()[i].rank)
                    .count()
                    >= 2
        })
        .collect();
    let remove: Vec<_> = (0..n).filter(|i| !pairs.contains(i)).take(5).collect();
    if !remove.is_empty() {
        masks.push(remove);
    }
    let mut low: Vec<_> = (0..n).collect();
    low.sort_by_key(|&i| run.hand()[i].rank.0);
    masks.push(low.into_iter().take(5).collect());
    masks.sort();
    masks.dedup();
    masks
        .into_iter()
        .filter(|g| valid_play(run, g))
        .map(|g| Move {
            action: "discard".into(),
            indices: g,
            slot: 0,
            label: String::new(),
        })
        .collect()
}
fn policy(run: &Run, probe_seed: &str) -> Option<Move> {
    let mut belief = run.clone();
    belief.reader_redeterminize(&format!("{probe_seed}-belief"));
    policy_on_belief(&belief, probe_seed)
}
fn policy_on_belief(run: &Run, probe_seed: &str) -> Option<Move> {
    let (play, score) = best_play(run, probe_seed)?;
    let need = (run.blind_chips() - run.chips()).max(0.);
    if score >= need {
        return Some(play);
    }
    let mut options = inventory_moves(
        run,
        &if run.consumables().is_empty() {
            vec![]
        } else {
            subsets(run.hand().len())
        },
    );
    if run.discards_left() > 0 {
        options.extend(discard_moves(run, &play));
    }
    // Bound continuation branching; the first action itself is compared exhaustively.
    // Keep one target choice per consumable pattern, chosen by visible card potential.
    options.sort_by(|a, b| cheap_value(run, &b.indices).total_cmp(&cheap_value(run, &a.indices)));
    let mut seen = std::collections::HashSet::new();
    options.retain(|m| m.action != "use" || seen.insert((m.slot, m.indices.len())));
    let mut best = play;
    let mut value = (score * run.hands_left() as f64).min(need);
    let mut speed = (need / score.max(1.)).ceil();
    for m in options {
        let mut probe = run.clone();
        probe.reader_redeterminize(probe_seed);
        if apply(&mut probe, &m).is_err() {
            continue;
        }
        if matches!(probe.state(), State::RoundEval | State::Won) {
            return Some(m);
        }
        if probe.state() != State::SelectingHand {
            continue;
        }
        let ps = best_play(&probe, &format!("{probe_seed}-after"))
            .map(|(_, s)| s)
            .unwrap_or(0.);
        let capacity =
            (ps * probe.hands_left() as f64).min((probe.blind_chips() - probe.chips()).max(0.));
        let projected = probe.chips() - run.chips() + capacity;
        let steps = ((probe.blind_chips() - probe.chips()).max(0.) / ps.max(1.)).ceil();
        if projected > value
            || (projected == value && steps < speed)
            || (projected == value
                && steps == speed
                && m.action == "discard"
                && best.action == "play")
        {
            best = m;
            value = projected;
            speed = steps;
        }
    }
    Some(best)
}

fn emit(value: &Value) {
    println!("{value}");
    io::stdout().flush().unwrap();
}
fn preference(a: &Value, b: &Value) -> std::cmp::Ordering {
    number(b, "win_probability", 0.)
        .total_cmp(&number(a, "win_probability", 0.))
        .then(
            number(a, "expected_hands_to_win", f64::INFINITY).total_cmp(&number(
                b,
                "expected_hands_to_win",
                f64::INFINITY,
            )),
        )
        .then(number(b, "expected_discards_used", 0.).total_cmp(&number(
            a,
            "expected_discards_used",
            0.,
        )))
        .then(number(a, "expected_inventory_spent", 0.).total_cmp(&number(
            b,
            "expected_inventory_spent",
            0.,
        )))
        .then(number(b, "score", 0.).total_cmp(&number(a, "score", 0.)))
        .then(a["action"].to_string().cmp(&b["action"].to_string()))
        .then(a["slot"].to_string().cmp(&b["slot"].to_string()))
        .then(a["indices"].to_string().cmp(&b["indices"].to_string()))
}
pub fn analyze(state: &Value, run: Run, trials: usize, seed: u64) -> Value {
    let started = Instant::now();
    let actions = root_moves(&run);
    let total = actions.len();
    let h = run.hands_left();
    let d = run.discards_left();
    let target = (run.blind_chips() - run.chips()).max(0.);
    let initial_chips = run.chips();
    let mut results = Vec::<Value>::new();
    let snapshot = |results: &Vec<Value>, done: usize, final_result: bool| {
        let mut ranked = results.clone();
        ranked.sort_by(preference);
        let select = |kind: &str| {
            ranked
                .iter()
                .filter(|r| r["action"] == kind)
                .take(5)
                .cloned()
                .collect::<Vec<_>>()
        };
        let best = ranked.first();
        let mut value = json!({"status":if final_result{"ready"}else{"running"},"partial":!final_result,
   "completed":done,"total":total,"plays":select("play"),"discards":select("discard"),
   "special_actions":ranked.iter().filter(|r|r["action"]!="play"&&r["action"]!="discard").take(5).cloned().collect::<Vec<_>>(),
   "play_options":results.iter().filter(|r|r["action"]=="play").count(),"discard_options":results.iter().filter(|r|r["action"]=="discard").count(),
   "trials_per_option":trials,"target":target,"hands_left":h,"discards_left":d,
   "hand_number":number(&state["round"],"hands_played",0.) as usize+1,"hands_after_next_play":h-1,
   "discards_after_action":d-i64::from(best.is_some_and(|r|r["action"]=="discard")),
   "hand_cards":cards(state,"hand"),"joker_cards":cards(state,"jokers"),"consumable_cards":cards(state,"consumables"),
   "elapsed_seconds":started.elapsed().as_secs_f64(),"planning_mode":"full_rules_rollouts",
   "scope":"Simula la ciega completa con las reglas del juego base: 150 comodines, 28 jefes, mejoras, ediciones, sellos y consumibles. Compara las primeras acciones; las continuaciones usan una estrategia aproximada, sin consultar el futuro de robo. El porcentaje no garantiza el óptimo global. Las cartas ocultas y el orden de comodines ocultos se muestrean como incertidumbre.",
   "score_mode":"Motor completo de reglas; fichas adicionales desde el estado actual y efectos aleatorios simulados."});
        if let Some(best) = best {
            value["recommendation"] = best.clone();
        }
        value
    };
    emit(&snapshot(&results, 0, false));
    let threads = std::thread::available_parallelism()
        .map(|n| n.get())
        .unwrap_or(1)
        .min(8)
        .min(total.max(1));
    let cursor = std::sync::atomic::AtomicUsize::new(0);
    let (tx, rx) = std::sync::mpsc::channel();
    std::thread::scope(|scope| {
        for _ in 0..threads {
            let tx = tx.clone();
            let actions = &actions;
            let cursor = &cursor;
            let run = &run;
            scope.spawn(move || loop {
                let i = cursor.fetch_add(1, std::sync::atomic::Ordering::Relaxed);
                if i >= actions.len() {
                    break;
                }
                let result = evaluate(run, &actions[i], trials, seed, h, initial_chips);
                if tx.send(result).is_err() {
                    break;
                }
            });
        }
        drop(tx);
        for result in rx {
            results.push(result);
            emit(&snapshot(&results, results.len(), false));
        }
    });
    snapshot(&results, total, true)
}

fn evaluate(run: &Run, m: &Move, trials: usize, seed: u64, h: i64, initial_chips: f64) -> Value {
    let mut wins = 0usize;
    let mut sum = 0.;
    let mut sum2 = 0.;
    let mut winning_hands = 0usize;
    let mut discards = 0usize;
    let mut inventory_spent = 0usize;
    let mut by_hands = vec![0usize; (h + 8).max(1) as usize];
    let mut scores = vec![];
    let mut immediate = 0.;
    for trial in 0..trials {
        let mut sim = run.clone();
        sim.reader_redeterminize(&format!("reader-{seed}-{trial}"));
        let initial_h = sim.hands_played_this_round();
        let initial_d = sim.discards_used_this_round();
        if apply(&mut sim, &m).is_err() {
            continue;
        }
        inventory_spent += usize::from(!matches!(m.action.as_str(), "play" | "discard"));
        if m.action == "play" {
            immediate += sim.last_play().map(|p| p.score).unwrap_or(0.);
        }
        // A finite guard also handles consumable creation/copy loops. Using a consumable
        // consumes one action; a safety cutoff is surfaced as a search approximation.
        for step in 0..63 {
            if sim.state() != State::SelectingHand {
                break;
            }
            if sim.hand().is_empty() {
                break;
            }
            let Some(next) = policy(&sim, &format!("probe-{seed}-{trial}-{step}")) else {
                break;
            };
            if apply(&mut sim, &next).is_err() {
                break;
            }
            inventory_spent += usize::from(!matches!(next.action.as_str(), "play" | "discard"));
        }
        let used_h = (sim.hands_played_this_round() - initial_h).max(0) as usize;
        // End-round reset preserves these counters in the simulator; include Mr Bones.
        let used_d = (sim.discards_used_this_round() - initial_d).max(0) as usize;
        let success = matches!(sim.state(), State::RoundEval | State::Won);
        if success {
            wins += 1;
            winning_hands += used_h;
            for (k, count) in by_hands.iter_mut().enumerate() {
                if used_h <= k + 1 {
                    *count += 1;
                }
            }
        }
        discards += used_d;
        let earned = (sim.chips() - initial_chips).max(0.);
        sum += earned;
        sum2 += earned * earned;
        scores.push(earned);
    }
    let n = trials as f64;
    let p = wins as f64 / n;
    let z = 1.96f64;
    let center = (p + z * z / (2. * n)) / (1. + z * z / n);
    let radius = z * (p * (1. - p) / n + z * z / (4. * n * n)).sqrt() / (1. + z * z / n);
    scores.sort_by(f64::total_cmp);
    let percentile = |q: f64| {
        scores
            .get(((scores.len().saturating_sub(1)) as f64 * q).round() as usize)
            .copied()
            .unwrap_or(0.)
    };
    let mut result = json!({"action":m.action,"indices":m.indices.iter().map(|i|i+1).collect::<Vec<_>>(),"slot":m.slot+1,"label":m.label,
   "score":sum/n,"win_probability":p,"expected_hands_to_win":if wins>0{json!(winning_hands as f64/wins as f64)}else{Value::Null},
   "expected_discards_used":discards as f64/n,"expected_inventory_spent":inventory_spent as f64/n,"trials":trials,"win_interval_95":[(center-radius).max(0.),(center+radius).min(1.)],
   "win_by_hands":by_hands[..(h as usize).max(1)].iter().map(|&x|x as f64/n).collect::<Vec<_>>(),
   "standard_error":((sum2/n-(sum/n).powi(2)).max(0.)/n).sqrt(),"p10":percentile(0.1),"p90":percentile(0.9)});
    if m.action == "play" {
        let play: Vec<_> = m.indices.iter().map(|&i| run.hand()[i]).collect();
        let (ht, _, _) = get_poker_hand_info(&play, &run.eval_mods());
        result["hand"] = json!(if play.iter().any(|c| c.face_down) {
            "Cartas ocultas"
        } else {
            hand_name(ht)
        });
        result["immediate_score"] = json!(immediate / n);
    }
    result
}
