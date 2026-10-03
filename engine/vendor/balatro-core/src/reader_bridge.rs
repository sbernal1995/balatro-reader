//! Extensions for the reader. Never connects to or mutates the real game.
use crate::deck::pseudoshuffle;
use crate::run::Run;

pub(crate) fn reader_deck_size() -> usize {
    52
}

impl Run {
    pub fn reader_refresh_debuffs(&mut self) {
        if let Some(blind) = &self.active_blind {
            let pareidolia = self
                .jokers
                .iter()
                .any(|j| j.id == crate::items::JokerId::Pareidolia && !j.debuffed);
            let smeared = self
                .jokers
                .iter()
                .any(|j| j.id == crate::items::JokerId::Smeared && !j.debuffed);
            for card in self
                .hand
                .iter_mut()
                .chain(self.deck.iter_mut())
                .chain(self.discard_pile.iter_mut())
            {
                card.debuff = blind.debuff_card(card, pareidolia, smeared);
            }
        }
    }
    pub fn reader_redeterminize(&mut self, seed: &str) {
        self.redeterminize(seed);
        let forced = self.forced_card_index();
        let hidden: Vec<usize> = self
            .hand
            .iter()
            .enumerate()
            .filter_map(|(i, c)| c.face_down.then_some(i))
            .collect();
        if !hidden.is_empty() {
            let mut bag = std::mem::take(&mut self.deck);
            bag.extend(hidden.iter().map(|&i| self.hand[i]));
            let s = self.rng.pseudoseed("reader_hidden_cards");
            pseudoshuffle(&mut bag, s);
            for i in hidden {
                let mut card = bag.pop().unwrap();
                card.face_down = true;
                self.hand[i] = card;
            }
            for card in &mut bag {
                card.face_down = false;
            }
            self.deck = bag;
            self.forced_card = forced.map(|i| self.hand[i].sort_id);
        }
        let slots: Vec<usize> = self
            .jokers
            .iter()
            .enumerate()
            .filter_map(|(i, j)| j.flipped.then_some(i))
            .collect();
        let mut js: Vec<_> = slots.iter().map(|&i| self.jokers[i].clone()).collect();
        // Shuffle hidden joker order without querying the original order.
        for i in (1..js.len()).rev() {
            let j = self.rng.random_range("reader_hidden_jokers", 0, i as i64) as usize;
            js.swap(i, j);
        }
        for (slot, j) in slots.into_iter().zip(js) {
            self.jokers[slot] = j;
        }
        self.reader_refresh_debuffs();
    }

    /// Arrange selected cards into the recommended scoring order. Returned
    /// indices refer to the private simulation's hand, never the live game.
    pub fn reader_play_order(&mut self, indices: &[usize]) -> Vec<usize> {
        let mut slots = indices.to_vec();
        slots.sort_unstable();
        let selected: Vec<_> = indices.iter().map(|&i| self.hand[i]).collect();
        for (&slot, card) in slots.iter().zip(selected) {
            self.hand[slot] = card;
        }
        slots
    }
}
