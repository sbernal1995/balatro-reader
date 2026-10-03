use balatro_core::{
    blinds::{blind_by_key, ActiveBlind},
    cards::{Card, Edition, Enhancement, HandType, Rank, Seal, Suit},
    items::{consumable_by_key, joker_by_key, JokerId},
    jokers::JokerState,
    run::Run,
    shop::{OwnedConsumable, OwnedJoker},
};
use serde_json::{json, Value};

pub fn number(v: &Value, key: &str, default: f64) -> f64 {
    v.get(key).and_then(Value::as_f64).unwrap_or(default)
}
pub fn text<'a>(v: &'a Value, key: &str, default: &'a str) -> &'a str {
    v.get(key).and_then(Value::as_str).unwrap_or(default)
}
pub fn cards(v: &Value, key: &str) -> Vec<Value> {
    v[key]["cards"].as_array().cloned().unwrap_or_default()
}
pub fn hand_name(h: HandType) -> &'static str {
    match h {
        HandType::HighCard => "High Card",
        HandType::Pair => "Pair",
        HandType::TwoPair => "Two Pair",
        HandType::ThreeOfAKind => "Three of a Kind",
        HandType::Straight => "Straight",
        HandType::Flush => "Flush",
        HandType::FullHouse => "Full House",
        HandType::FourOfAKind => "Four of a Kind",
        HandType::StraightFlush => "Straight Flush",
        HandType::FiveOfAKind => "Five of a Kind",
        HandType::FlushHouse => "Flush House",
        HandType::FlushFive => "Flush Five",
    }
}
pub fn hand_type(s: &str) -> Option<HandType> {
    HandType::ALL
        .into_iter()
        .find(|h| hand_name(*h) == s || format!("{h:?}") == s)
}
fn suit(s: &str) -> Result<Suit, String> {
    match s {
        "H" | "Hearts" => Ok(Suit::Hearts),
        "D" | "Diamonds" => Ok(Suit::Diamonds),
        "C" | "Clubs" => Ok(Suit::Clubs),
        "S" | "Spades" => Ok(Suit::Spades),
        _ => Err(format!("Palo desconocido: {s}")),
    }
}
fn rank(s: &str) -> Result<u8, String> {
    match s {
        "A" => Ok(14),
        "K" => Ok(13),
        "Q" => Ok(12),
        "J" => Ok(11),
        "T" => Ok(10),
        _ => s
            .parse::<u8>()
            .ok()
            .filter(|r| (2..=14).contains(r))
            .ok_or(format!("Valor desconocido: {s}")),
    }
}
fn norm(s: &str) -> String {
    s.to_uppercase()
        .trim_start_matches("M_")
        .trim_start_matches("E_")
        .replace(" CARD", "")
}
pub fn playing_card(c: &Value, default_id: u32) -> Result<Card, String> {
    let a = &c["ability"];
    let m = &c["modifier"];
    let v = &c["value"];
    let mut result = Card::new(
        Rank(rank(text(v, "rank", ""))?),
        suit(text(v, "suit", ""))?,
        number(c, "id", default_id as f64) as u32,
    );
    result.enhancement = match norm(text(m, "enhancement", "")).as_str() {
        "" | "BASE" => Enhancement::None,
        "BONUS" => Enhancement::Bonus,
        "MULT" => Enhancement::Mult,
        "WILD" => Enhancement::Wild,
        "GLASS" => Enhancement::Glass,
        "STEEL" => Enhancement::Steel,
        "STONE" => Enhancement::Stone,
        "GOLD" => Enhancement::Gold,
        "LUCKY" => Enhancement::Lucky,
        x => return Err(format!("Mejora fuera del juego base: {x}")),
    };
    result.edition = edition(m)?;
    result.seal = match norm(text(m, "seal", "")).as_str() {
        "" => Seal::None,
        "RED" => Seal::Red,
        "BLUE" => Seal::Blue,
        "PURPLE" => Seal::Purple,
        "GOLD" => Seal::Gold,
        x => return Err(format!("Sello fuera del juego base: {x}")),
    };
    result.debuff =
        c["state"]["debuff"].as_bool().unwrap_or(false) || a["debuff"].as_bool().unwrap_or(false);
    result.face_down = c["state"]["hidden"].as_bool().unwrap_or(false);
    result.played_this_ante = a["played_this_ante"].as_bool().unwrap_or(false);
    result.perma_bonus = number(a, "perma_bonus", 0.) as i64;
    Ok(result)
}
fn edition(m: &Value) -> Result<Edition, String> {
    Ok(match norm(text(m, "edition", "")).as_str() {
        "" => Edition::None,
        "FOIL" => Edition::Foil,
        "HOLO" => Edition::Holo,
        "POLYCHROME" => Edition::Polychrome,
        "NEGATIVE" => Edition::Negative,
        x => return Err(format!("Edición fuera del juego base: {x}")),
    })
}
fn joker(c: &Value, default_id: u32) -> Result<OwnedJoker, String> {
    let key = text(c, "key", "");
    let id = joker_by_key(key)
        .ok_or(format!("Comodín fuera del juego base: {key}"))?
        .id;
    let a = &c["ability"];
    let e = &a["extra"];
    let mut state = JokerState::initial(id);
    state.mult = number(a, "mult", state.mult);
    state.chips = number(e, "chips", state.chips);
    state.x_mult = number(a, "x_mult", number(a, "Xmult", state.x_mult));
    state.extra = match id {
        JokerId::Rocket => number(e, "dollars", state.extra),
        JokerId::TurtleBean => number(e, "h_size", state.extra),
        JokerId::Yorick => number(a, "yorick_discards", state.extra),
        JokerId::Caino => number(a, "caino_xmult", state.extra),
        JokerId::Invisible => number(a, "invis_rounds", state.extra),
        _ => e.as_f64().unwrap_or(state.extra),
    };
    state.to_do_hand =
        hand_type(text(a, "to_do_poker_hand", "High Card")).unwrap_or(HandType::HighCard);
    Ok(OwnedJoker {
        id,
        edition: edition(&c["modifier"])?,
        sort_id: number(c, "id", default_id as f64) as u32,
        extra_value: number(a, "extra_value", 0.) as i64,
        debuffed: c["state"]["debuff"].as_bool().unwrap_or(false),
        flipped: c["state"]["hidden"].as_bool().unwrap_or(false),
        eternal: a["eternal"].as_bool().unwrap_or(false),
        rental: a["rental"].as_bool().unwrap_or(false),
        perish_tally: if a["perishable"].as_bool().unwrap_or(false) {
            Some(number(a, "perish_tally", 5.) as i64)
        } else {
            None
        },
        hands_at_create: number(a, "hands_played_at_create", 0.) as i64,
        state,
    })
}

pub fn import(v: &Value) -> Result<Run, String> {
    let r = &v["round"];
    let ctx = &v["joker_context"];
    let cr = &ctx["current_round"];
    let resets = &ctx["round_resets"];
    let blind = v["blinds"]
        .as_object()
        .and_then(|b| b.values().find(|b| b["status"] == "CURRENT"))
        .ok_or("No se pudo identificar la ciega actual.")?;
    let live = &v["active_blind"];
    let key = text(
        live,
        "key",
        text(
            blind,
            "key",
            if blind["type"] == "BOSS" {
                ""
            } else if blind["type"] == "BIG" {
                "bl_big"
            } else {
                "bl_small"
            },
        ),
    );
    let proto = blind_by_key(key).ok_or(format!(
        "Ciega fuera del juego base o falta su clave: {key}. Actualizá el mod y reiniciá Balatro."
    ))?;
    let mut active = ActiveBlind::new(proto, number(v, "ante_num", 1.) as i64);
    active.chips = number(live, "chips", number(blind, "score", 0.));
    active.disabled = live["disabled"]
        .as_bool()
        .unwrap_or(ctx["blind"]["disabled"].as_bool().unwrap_or(false));
    active.prepped = live["prepped"].as_bool().unwrap_or(active.prepped);
    active.triggered = live["triggered"].as_bool().unwrap_or(false);
    active.only_hand = hand_type(text(live, "only_hand", ""));
    active.discards_sub = number(live, "discards_sub", 0.) as i64;
    active.hands_sub = number(live, "hands_sub", 0.) as i64;
    for (i, ht) in HandType::ALL.iter().enumerate() {
        active.eye_hands[i] = live["hands"][hand_name(*ht)].as_bool().unwrap_or(false);
    }
    let mut run = serde_json::to_value(Run::new("reader-template")).map_err(|e| e.to_string())?;
    run["state"] = json!("SelectingHand");
    run["active_blind"] = serde_json::to_value(active).unwrap();
    run["blind_on_deck"] = json!(if proto.is_boss {
        "Boss"
    } else if key == "bl_big" {
        "Big"
    } else {
        "Small"
    });
    run["reader_plasma"] = json!(matches!(
        text(v, "deck", "").to_uppercase().as_str(),
        "PLASMA" | "B_PLASMA"
    ));
    run["reader_rental_rate"] = json!(number(ctx, "rental_rate", 3.) as i64);
    run["reader_starting_deck_size"] = json!(number(ctx, "starting_deck_size", 52.) as usize);
    run["reader_excluded_jokers"] =
        json!(v["excluded_jokers"].as_array().cloned().unwrap_or_default());
    for (key, default) in [("discount_percent", 0.), ("edition_rate", 1.)] {
        let n = number(ctx, key, default);
        run[key] = if key == "discount_percent" {
            json!(n as i64)
        } else {
            json!(n)
        };
    }
    for (dest, src, src_key, default) in [
        ("hands_left", r, "hands_left", 4.),
        ("discards_left", r, "discards_left", 3.),
        ("chips", r, "chips", 0.),
        ("ante", v, "ante_num", 1.),
        ("round", v, "round_num", 1.),
        ("dollars", v, "money", 0.),
        (
            "hand_size",
            &v["hand"],
            "limit",
            cards(v, "hand").len() as f64,
        ),
        ("hands_played_round", r, "hands_played", 0.),
        ("discards_used_round", r, "discards_used", 0.),
        ("hands_played_total", ctx, "hands_played", 0.),
        ("skips", ctx, "skips", 0.),
        ("bankrupt_at", ctx, "bankrupt_at", 0.),
        ("round_resets_hands", resets, "hands", 4.),
        ("round_resets_discards", resets, "discards", 3.),
        ("ecto_minus", ctx, "ecto_minus", 1.),
        ("interest_cap", ctx, "interest_cap", 25.),
        ("interest_amount", ctx, "interest_amount", 1.),
        ("joker_slots", &v["jokers"], "limit", 5.),
        ("consumable_slots", &v["consumables"], "limit", 2.),
    ] {
        let n = number(src, src_key, default);
        run[dest] = if dest == "chips" {
            json!(n)
        } else {
            json!(n as i64)
        };
    }
    run["blind_ante"] = run["ante"].clone();
    run["prob_normal"] = json!(number(&ctx["probabilities"], "normal", 1.));
    run["tarots_used"] = json!(number(&ctx["consumeable_usage_total"], "tarot", 0.) as i64);
    run["last_hand_played"] = json!(hand_type(text(ctx, "last_hand_played", "")));
    run["most_played_hand"] =
        json!(hand_type(text(cr, "most_played_poker_hand", "High Card"))
            .unwrap_or(HandType::HighCard));
    run["last_tarot_planet"] = if ctx["last_tarot_planet"].is_string() {
        ctx["last_tarot_planet"].clone()
    } else {
        Value::Null
    };
    let mut hand = cards(v, "hand");
    let mut deck = cards(v, "draw_pool");
    deck.sort_by_key(Value::to_string);
    let hidden: Vec<_> = hand
        .iter()
        .enumerate()
        .filter_map(|(i, c)| c["state"]["hidden"].as_bool().unwrap_or(false).then_some(i))
        .collect();
    if !hidden.is_empty() {
        let mut bag = v["unseen_cards"].as_array().cloned().ok_or(
            "Falta la composición anónima para evaluar cartas ocultas. Actualizá el lector.",
        )?;
        if bag.len() != hidden.len() + deck.len() {
            return Err(
                "La composición de cartas ocultas no coincide con la mano y la pila.".into(),
            );
        }
        for i in hidden {
            let mut c = bag.pop().unwrap();
            c["state"] = hand[i]["state"].clone();
            c["id"] = json!(100000 + i);
            hand[i] = c;
        }
        deck = bag;
    }
    let mut next_id = 1000u32;
    for (name, area) in [
        ("hand", hand),
        ("deck", deck),
        ("discard_pile", cards(v, "discard_pool")),
    ] {
        let converted: Result<Vec<_>, _> = area
            .iter()
            .map(|c| {
                next_id += 1;
                playing_card(c, next_id)
            })
            .collect();
        run[name] = serde_json::to_value(converted?).unwrap();
    }
    let mut js = cards(v, "jokers");
    if let Some(unknown) = v["unknown_jokers"].as_array() {
        let mut j = unknown.iter();
        for c in &mut js {
            if c["state"]["hidden"].as_bool().unwrap_or(false) {
                *c = j.next().ok_or("Faltan comodines ocultos")?.clone();
                c["state"]["hidden"] = json!(true);
            }
        }
    }
    let jokers: Result<Vec<_>, _> = js
        .iter()
        .enumerate()
        .map(|(i, c)| joker(c, 200000 + i as u32))
        .collect();
    let jokers = jokers?;
    let mut used = std::collections::HashMap::<String, u32>::new();
    for j in &jokers {
        *used.entry(j.id.key().to_string()).or_default() += 1;
    }
    run["jokers"] = serde_json::to_value(jokers).unwrap();
    let mut cs = Vec::new();
    for (i, c) in cards(v, "consumables").iter().enumerate() {
        let key = text(c, "key", "");
        let (meta, _) =
            consumable_by_key(key).ok_or(format!("Consumible fuera del juego base: {key}"))?;
        cs.push(OwnedConsumable {
            key: meta.key,
            sort_id: number(c, "id", 300000. + i as f64) as u32,
            negative: edition(&c["modifier"])? == Edition::Negative,
            extra_value: number(&c["ability"], "extra_value", 0.) as i64,
        });
    }
    for c in &cs {
        *used.entry(c.key.to_string()).or_default() += 1;
    }
    run["used_keys"] = json!(used);
    run["consumables"] = serde_json::to_value(cs).unwrap();
    run["used_vouchers"] = json!(v["used_vouchers"]
        .as_object()
        .map(|m| m.keys().cloned().collect::<Vec<_>>())
        .unwrap_or_default());
    run["pool_flags"] = json!(ctx["pool_flags"]
        .as_object()
        .map(|m| m
            .iter()
            .filter(|(_, v)| **v == json!(true))
            .map(|(k, _)| k.clone())
            .collect::<Vec<_>>())
        .unwrap_or_default());
    run["consumable_usage"] = json!(ctx["consumeable_usage"]
        .as_object()
        .map(|m| m
            .iter()
            .map(|(k, u)| (
                k.clone(),
                number(u, "count", u.as_f64().unwrap_or(0.)) as u32
            ))
            .collect::<Vec<_>>())
        .unwrap_or_default());
    for (dest, src) in [
        ("mail_card_id", "mail_card"),
        ("castle_suit", "castle_card"),
        ("ancient_suit", "ancient_card"),
    ] {
        if dest == "mail_card_id" {
            if cr[src]["id"].is_number() {
                run[dest] = cr[src]["id"].clone();
            }
        } else if let Ok(s) = suit(text(&cr[src], "suit", "")) {
            run[dest] = json!(s);
        }
    }
    if let Ok(s) = suit(text(&cr["idol_card"], "suit", "")) {
        run["idol_card"] = json!([number(&cr["idol_card"], "id", 14.) as u8, s]);
    }
    let mut max_id = next_id;
    for area in ["hand", "deck", "discard_pile", "jokers", "consumables"] {
        if let Some(list) = run[area].as_array() {
            for c in list {
                max_id = max_id.max(number(c, "sort_id", 0.) as u32);
            }
        }
    }
    run["sort_id_counter"] = json!(max_id + 1);
    run["playing_card_counter"] = json!(number(ctx, "playing_card", max_id as f64) as u32);
    if let Some(i) = cards(v, "hand").iter().position(|c| {
        c["ability"]["forced_selection"].as_bool().unwrap_or(false)
            || c["state"]["forced_selection"].as_bool().unwrap_or(false)
    }) {
        run["forced_card"] = run["hand"][i]["sort_id"].clone();
    } else {
        run["forced_card"] = Value::Null;
    }
    for (i, ht) in HandType::ALL.iter().enumerate() {
        let h = &v["hands"][hand_name(*ht)];
        for key in ["level", "chips", "mult", "played", "played_this_round"] {
            if h[key].is_number() {
                run["hands_table"]["rows"][i][key] = h[key].clone();
            }
        }
        if h["visible"].is_boolean() {
            run["hands_table"]["rows"][i]["visible"] = h["visible"].clone();
        }
    }
    let mut imported: Run =
        serde_json::from_value(run).map_err(|e| format!("Estado incompleto para el motor: {e}"))?;
    imported.reader_refresh_debuffs();
    Ok(imported)
}
