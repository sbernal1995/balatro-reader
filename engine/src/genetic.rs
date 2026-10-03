//! Bounded genetic search over legal first actions. Future draws remain sampled.
use crate::search::{preference, Move};
use serde_json::Value;
use std::collections::HashSet;

pub const POPULATION: usize = 24;
pub const ELITES: usize = 6;
pub const GENERATIONS: usize = 5;
pub const BUDGET: usize = POPULATION + (POPULATION - ELITES) * (GENERATIONS - 1);

struct Random(u64);
impl Random {
    fn next(&mut self) -> u64 {
        self.0 = self.0.wrapping_add(0x9e3779b97f4a7c15);
        let mut z = self.0;
        z = (z ^ (z >> 30)).wrapping_mul(0xbf58476d1ce4e5b9);
        z = (z ^ (z >> 27)).wrapping_mul(0x94d049bb133111eb);
        z ^ (z >> 31)
    }
    fn index(&mut self, n: usize) -> usize {
        self.next() as usize % n
    }
}

pub struct Search {
    rng: Random,
    visited: HashSet<usize>,
    pub generation: usize,
    pub budget: usize,
}
impl Search {
    pub fn new(total: usize, seed: u64) -> Self {
        Self {
            rng: Random(seed ^ 0x47454e45544943),
            visited: HashSet::new(),
            generation: 0,
            budget: total.min(BUDGET),
        }
    }
    fn random_unseen(&mut self, total: usize) -> Option<usize> {
        let start = self.rng.index(total);
        (0..total)
            .map(|n| (start + n) % total)
            .find(|i| !self.visited.contains(i))
    }
    pub fn initial(&mut self, actions: &[Move], seeds: &[usize]) -> Vec<usize> {
        if actions.is_empty() {
            return vec![];
        }
        let limit = POPULATION.min(self.budget);
        let mut batch = vec![];
        for &i in seeds {
            if batch.len() == limit {
                break;
            }
            if i < actions.len() && self.visited.insert(i) {
                batch.push(i);
            }
        }
        while batch.len() < limit {
            let Some(i) = self.random_unseen(actions.len()) else {
                break;
            };
            self.visited.insert(i);
            batch.push(i);
        }
        self.generation = usize::from(!batch.is_empty());
        batch
    }
    fn parent(&mut self, ranked: &[(usize, Value)]) -> usize {
        let pool = ranked.len().min(POPULATION);
        let rank = (0..3).map(|_| self.rng.index(pool)).min().unwrap();
        ranked[rank].0
    }
    pub fn next(
        &mut self,
        actions: &[Move],
        evaluated: &[(usize, Value)],
        hand_size: usize,
    ) -> Vec<usize> {
        if self.visited.len() >= self.budget || evaluated.is_empty() {
            return vec![];
        }
        let mut ranked = evaluated.to_vec();
        ranked.sort_by(|a, b| preference(&a.1, &b.1).then(a.0.cmp(&b.0)));
        let count = (POPULATION - ELITES).min(self.budget - self.visited.len());
        let mut batch = vec![];
        for _ in 0..count {
            let a = self.parent(&ranked);
            let b = self.parent(&ranked);
            let mut family = if self.rng.index(2) == 0 { a } else { b };
            let mut cards: Vec<_> = (0..hand_size)
                .filter(|i| {
                    let parent = if self.rng.index(2) == 0 { a } else { b };
                    actions[parent].indices.contains(i)
                })
                .collect();
            // Mutation changes a selected card or an action/consumable family.
            if hand_size > 0 && self.rng.index(100) < 40 {
                let card = self.rng.index(hand_size);
                if cards.contains(&card) {
                    cards.retain(|&i| i != card);
                } else {
                    cards.push(card);
                }
            }
            if self.rng.index(100) < 20 {
                family = self.rng.index(actions.len());
            }
            // Repair against the legal action list: no invalid hand sizes, targets or sales.
            let candidates: Vec<_> = actions
                .iter()
                .enumerate()
                .filter(|(i, m)| {
                    !self.visited.contains(i)
                        && m.action == actions[family].action
                        && m.slot == actions[family].slot
                })
                .map(|(i, m)| {
                    let distance = m.indices.iter().filter(|i| !cards.contains(i)).count()
                        + cards.iter().filter(|i| !m.indices.contains(i)).count();
                    (distance, self.rng.next(), i)
                })
                .collect();
            let chosen = if self.rng.index(100) < 10 {
                self.random_unseen(actions.len())
            } else {
                candidates
                    .into_iter()
                    .min()
                    .map(|(_, _, i)| i)
                    .or_else(|| self.random_unseen(actions.len()))
            };
            if let Some(i) = chosen {
                self.visited.insert(i);
                batch.push(i);
            }
        }
        self.generation += usize::from(!batch.is_empty());
        batch
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;
    fn actions() -> Vec<Move> {
        (0..120)
            .map(|i| Move {
                action: if i % 2 == 0 { "play" } else { "discard" }.into(),
                indices: vec![i % 8],
                slot: 0,
                label: String::new(),
            })
            .collect()
    }
    fn search(seed: u64) -> Vec<usize> {
        let actions = actions();
        let mut search = Search::new(actions.len(), seed);
        let mut batch = search.initial(&actions, &[0, 1]);
        let mut visited = vec![];
        let mut evaluated = vec![];
        while !batch.is_empty() {
            for &i in &batch {
                evaluated.push((i, json!({"win_probability":i as f64/120.})));
            }
            visited.extend(batch);
            batch = search.next(&actions, &evaluated, 8);
        }
        assert_eq!(search.generation, GENERATIONS);
        visited
    }
    #[test]
    fn bounded_reproducible_and_no_repeated_evaluations() {
        let first = search(123);
        assert_eq!(first.len(), BUDGET);
        assert_eq!(first.iter().copied().collect::<HashSet<_>>().len(), BUDGET);
        assert!(first.iter().all(|&i| i < 120));
        assert_eq!(first, search(123));
        assert_ne!(first, search(456));
    }
    #[test]
    fn small_search_covers_every_legal_action_and_empty_search_stops() {
        let actions = &actions()[..7];
        let mut s = Search::new(actions.len(), 42);
        let batch = s.initial(actions, &[0, 1, 1, 999]);
        assert_eq!(batch.len(), 7);
        assert!(s.next(actions, &[], 8).is_empty());
        assert!(Search::new(0, 42).initial(&[], &[]).is_empty());
    }
}
