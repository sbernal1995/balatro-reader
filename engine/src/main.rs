mod genetic;
mod import;
mod search;
use serde_json::{json, Value};
use std::io::{self, BufRead, Write};
fn main() {
    for line in io::stdin().lock().lines() {
        let result = line
            .map_err(|e| e.to_string())
            .and_then(|s| serde_json::from_str::<Value>(&s).map_err(|e| e.to_string()))
            .and_then(|v| dispatch(v));
        println!(
            "{}",
            match result {
                Ok(v) => v,
                Err(e) => json!({"status":"blocked","reason":e}),
            }
        );
        io::stdout().flush().unwrap();
    }
}
fn dispatch(v: Value) -> Result<Value, String> {
    if v["op"] == "catalog" {
        return Ok(json!({
  "search_modes":["exhaustive","genetic"],
  "jokers":balatro_core::items::JOKERS.iter().map(|j|j.key).collect::<Vec<_>>(),
  "bosses":balatro_core::blinds::BOSSES.iter().map(|b|b.key).collect::<Vec<_>>(),
  "consumables":balatro_core::items::TAROTS.iter().chain(balatro_core::items::PLANETS.iter()).chain(balatro_core::items::SPECTRALS.iter()).map(|c|c.key).collect::<Vec<_>>() }));
    }
    let state = &v["state"];
    let mut run = import::import(state)?;
    match v["op"].as_str().unwrap_or("analyze") {
        "import" => serde_json::to_value(run).map_err(|e| e.to_string()),
        "moves" => serde_json::to_value(search::root_moves(&run)).map_err(|e| e.to_string()),
        "step" => {
            let m: search::Move =
                serde_json::from_value(v["move"].clone()).map_err(|e| e.to_string())?;
            search::apply(&mut run, &m)?;
            serde_json::to_value(run).map_err(|e| e.to_string())
        }
        "analyze" => {
            let trials = v["trials"].as_u64().unwrap_or(1000).clamp(1, 1000) as usize;
            let seed = v["seed"].as_u64().unwrap_or(20261003);
            let algorithm = v["algorithm"].as_str().unwrap_or("exhaustive");
            if !matches!(algorithm, "exhaustive" | "genetic") {
                return Err("Algoritmo desconocido.".into());
            }
            Ok(search::analyze(
                state,
                run,
                trials,
                seed,
                algorithm == "genetic",
            ))
        }
        _ => Err("Operación desconocida.".into()),
    }
}
