"""Observable-state continuations for finite-round Monte Carlo.

Tiny rounds use exact expectimax. Larger rounds use an adaptive rollout policy:
it observes the current hand and independently samples a possible draw to choose
between playing and discarding. It never inspects the rollout's future draws.
The exhaustive first-action comparison is empirical, not an optimality proof.
"""
import itertools
import math
from functools import lru_cache

import numpy as np


def preference(option):
    """Win chance, fewer winning hands, then use available discards."""
    hands = option['expected_hands_to_win']
    return (-option['win_probability'], hands if hands is not None else math.inf,
            -option['expected_discards_used'], -option['score'],
            option['action'] != 'discard', len(option['indices']), option['indices'])


class RoundPlanner:
    def __init__(self, evaluator, hand_size, pool_size, hands_left, discards_left, target):
        self.ev = evaluator
        self.capacity = hand_size
        self.pool_size = pool_size
        self.hands_left = hands_left
        self.discards_left = discards_left
        self.target = target
        self.sentinel = len(evaluator.cards)-1
        self.greens = [j for j in evaluator.jokers
                       if j['key'] == 'j_green_joker' and not j.get('state', {}).get('debuff')]
        self.green_initial = np.array([j['ability'].get('mult', 0) for j in self.greens], float)
        self.green_gain = np.array([j['ability'].get('extra', {}).get('hand_add', 1)
                                    for j in self.greens], float)
        self.green_loss = np.array([j['ability'].get('extra', {}).get('discard_sub', 1)
                                    for j in self.greens], float)
        # Keep exact planning small enough for an interactive local application.
        self.exact = hand_size + pool_size <= 7 and hands_left + discards_left <= 7
        self._exact_value = lru_cache(maxsize=50000)(self._value)

    def scoring(self, hands, discards, remaining, green):
        return self.ev.scores(hands, np.asarray(discards)[:, None],
                              np.asarray(remaining)[:, None], green)

    def _value(self, hand, pool, h, d, need, green):
        # p(win), E[hands * win], E[discards used]. All decisions use observable sets.
        if need <= 0:
            return (1., 0., 0.), None
        if h <= 0 or not hand:
            return (0., 0., 0.), None
        scores, _, groups = self.ev.scores(np.array([hand]), d, len(pool), np.array([green]))
        best_value, best_action, best_key = None, None, None
        for action in ('play', 'discard'):
            if action == 'discard' and not d:
                continue
            limit = self.ev.limit if action == 'play' else 5
            options = groups if action == 'play' else [c for k in range(1, min(limit,len(hand))+1)
                        for c in itertools.combinations(range(len(hand)), k)]
            for i, remove in enumerate(options):
                earned = float(scores[0,i]) if action == 'play' else 0.
                retained = tuple(v for k,v in enumerate(hand) if k not in remove)
                nh, nd = h-int(action == 'play'), d-int(action == 'discard')
                ng = tuple(np.array(green)+self.green_gain if action == 'play'
                           else np.maximum(0,np.array(green)-self.green_loss))
                draw_count = min(self.capacity-len(retained),len(pool))
                if action == 'discard' and not retained and not draw_count:
                    continue
                if earned >= need:
                    value = (1., 1., 0.)
                else:
                    # Enumerate sets, never hidden deck order. Future decisions happen after drawing.
                    outcomes = itertools.combinations(pool, draw_count)
                    weight = math.comb(len(pool),draw_count)
                    value = np.zeros(3)
                    for drawn in outcomes:
                        rest = tuple(c for c in pool if c not in drawn)
                        child,_ = self._exact_value(tuple(sorted(retained+drawn)), rest,
                                                   nh,nd,need-earned,ng)
                        value += np.array(child)+[0,child[0]*int(action=='play'),int(action=='discard')]
                    value = tuple(value/weight)
                key = (-value[0],value[1]/value[0] if value[0] else math.inf,
                       -value[2],-earned,action!='discard',len(remove),remove)
                if best_key is None or key < best_key:
                    best_value,best_action,best_key = value,(action,remove),key
        return (best_value or (0.,0.,0.)),best_action

    def discard_mask(self, hands, best_indices, groups, available):
        """Choose a promising retained pattern from currently visible cards only."""
        n,width = hands.shape
        valid = hands != self.sentinel
        ranks = self.ev.cards[hands,0]
        suits = self.ev.cards[hands,1]
        keep_best = np.zeros_like(valid)
        for row,index in enumerate(best_indices):
            keep_best[row,list(groups[index])] = True
        # Retain the scoring hand, pairs, a flush draw, or a straight draw.
        same = (ranks[:,:,None] == ranks[:,None,:]) & valid[:,:,None] & valid[:,None,:]
        keep_pair = (same.sum(axis=2)>=2) & (ranks>0)
        suit_count = np.stack([((suits==s)&valid).sum(axis=1) for s in range(1,5)],axis=1)
        suit_choice = suit_count.argmax(axis=1)+1
        keep_flush = (suits==suit_choice[:,None]) & valid
        windows = [set(range(r,r+5)) for r in range(2,11)]+[{14,2,3,4,5}]
        straight_masks = np.stack([np.isin(ranks,list(w))&valid for w in windows],axis=1)
        # Count distinct ranks, so duplicate pairs cannot masquerade as a straight draw.
        counts = np.stack([sum(np.any((ranks==r)&valid,axis=1) for r in w) for w in windows],axis=1)
        keep_straight = straight_masks[np.arange(n),counts.argmax(axis=1)]
        # Higher-level hands get priority; partial draws must have at least 3 cards.
        best = keep_best.copy()
        values = np.zeros(n)
        for keep,kind,min_count in [(keep_pair,1,2),(keep_flush,5,3),(keep_straight,4,3)]:
            count = keep.sum(axis=1)
            # Expected completion from composition, rather than the future permutation.
            if kind == 1:
                need = np.any((self.ev.cards[self.capacity:,0][None,:,None] == ranks[:,None,:]) & keep[:,None,:],axis=2)
            elif kind == 5:
                need = self.ev.cards[self.capacity:-1,1][None,:] == suit_choice[:,None]
            else:
                chosen = counts.argmax(axis=1)
                need = np.stack([np.isin(self.ev.cards[self.capacity:-1,0],list(w)) for w in windows])[chosen]
            if kind == 1:
                need = need[:,:self.pool_size]
            outs = (need & available).sum(axis=1)
            potential = (self.ev.base_chips[kind]+count*9)*self.ev.base_mult[kind]
            value = potential * (outs/np.maximum(1,available.sum(axis=1))) ** np.maximum(1,5-count)
            eligible = (count>=min_count)&(count<valid.sum(axis=1))&(value>values)
            best[eligible] = keep[eligible]
            values[eligible] = value[eligible]
        remove = valid & ~best
        # If no spare card exists, try the lowest card; actual discard costs are scored below.
        empty = ~remove.any(axis=1)
        lowest = np.where(valid,ranks,np.inf).argmin(axis=1)
        remove[np.arange(n)[empty],lowest[empty]] = True
        # The game allows at most five discarded cards, even with a larger hand.
        order = np.argsort(np.where(remove,ranks,np.inf),axis=1,kind='stable')
        limited = np.zeros_like(remove)
        np.put_along_axis(limited,order[:,:5],np.take_along_axis(remove,order[:,:5],axis=1),axis=1)
        return limited

    def refill(self, hands, remove, draws):
        result = np.full_like(hands,self.sentinel)
        for row in range(len(hands)):
            retained = hands[row,(~remove[row])&(hands[row]!=self.sentinel)]
            result[row,:len(retained)] = retained
            drawn = draws[row]
            drawn = drawn[drawn!=self.sentinel][:self.capacity-len(retained)]
            result[row,len(retained):len(retained)+len(drawn)] = drawn
        return result

    def simulate(self, action, indices, permutations, seed, cancelled=None, trace=None):
        n = len(permutations)
        hands = np.tile(np.arange(self.capacity),(n,1))
        available = np.ones((n,self.pool_size),bool)
        cursor = np.zeros(n,int)
        h = np.full(n,self.hands_left,int)
        d = np.full(n,self.discards_left,int)
        total_score = np.zeros(n)
        used_h = np.zeros(n,int)
        used_d = np.zeros(n,int)
        green = np.tile(self.green_initial,(n,1))
        rng = np.random.default_rng(seed)
        first = True
        # Every action consumes a resource, so the horizon is finite.
        for step in range(self.hands_left+self.discards_left):
            if cancelled and cancelled():
                return None
            active = (total_score<self.target)&(h>0)&np.any(hands!=self.sentinel,axis=1)
            if not active.any():
                break
            rows = np.flatnonzero(active)
            current = hands[rows]
            remaining = available[rows].sum(axis=1)
            scores,_,groups = self.scoring(current,d[rows],remaining,green[rows])
            need = self.target-total_score[rows]
            chosen = scores.argmax(axis=1)
            # Win with the smallest current subset when possible, retaining spare cards.
            can_win = scores>=need[:,None]
            immediate = can_win.any(axis=1)
            chosen[immediate] = can_win[immediate].argmax(axis=1)
            remove = np.zeros_like(current,dtype=bool)
            for row,index in enumerate(chosen):
                remove[row,list(groups[index])] = True
            is_discard = np.zeros(len(rows),bool)
            if first:
                remove[:] = False
                remove[:,indices] = True
                is_discard[:] = action=='discard'
            elif self.exact:
                for row,global_row in enumerate(rows):
                    visible = tuple(sorted(current[row,current[row]!=self.sentinel]))
                    pool = tuple(np.flatnonzero(available[global_row])+self.capacity)
                    _,decision = self._exact_value(visible,pool,int(h[global_row]),int(d[global_row]),
                                                  float(need[row]),tuple(green[global_row]))
                    if decision:
                        kind,positions = decision
                        physical = [visible[p] for p in positions]
                        remove[row] = np.isin(current[row],physical)
                        is_discard[row] = kind=='discard'
            else:
                eligible = (d[rows]>0)&~immediate
                if eligible.any():
                    er = np.flatnonzero(eligible)
                    proposed = self.discard_mask(current[er],chosen[er],groups,available[rows[er]])
                    # Independent policy probe. It cannot reveal any actual future draw.
                    keys = rng.random((len(er),self.pool_size))
                    keys[~available[rows[er]]] = np.inf
                    order = np.argsort(keys,axis=1)[:,:min(5,self.pool_size)]
                    draws = order+self.capacity
                    counts = np.minimum(proposed.sum(axis=1),remaining[er])
                    draws[np.arange(draws.shape[1])[None,:]>=counts[:,None]] = self.sentinel
                    probe = self.refill(current[er],proposed,draws)
                    ng = np.maximum(0,green[rows[er]]-self.green_loss)
                    ps,_,_,_ = self.ev.best(probe,(d[rows[er]]-1)[:,None],
                                             (remaining[er]-counts)[:,None],ng)
                    cs = scores[np.arange(len(rows)),chosen][er]
                    # Project accumulation over all available hands; cost-sensitive and adaptive.
                    discard_capacity = ps*h[rows[er]]
                    play_capacity = cs*h[rows[er]]
                    better_chance = np.minimum(discard_capacity,need[er])>np.minimum(play_capacity,need[er])
                    fewer_hands = np.ceil(need[er]/np.maximum(1,ps))<np.ceil(need[er]/np.maximum(1,cs))
                    same = (ps==cs)&(discard_capacity>=need[er])
                    use = better_chance|fewer_hands|same
                    selected = er[use]
                    remove[selected] = proposed[use]
                    is_discard[selected] = True
            if trace:
                trace(step,rows.copy(),current.copy(),remove.copy(),is_discard.copy())
            # Score exactly the action selected (including Green Joker's before event).
            earned = np.zeros(len(rows))
            for row in np.flatnonzero(~is_discard):
                group = tuple(np.flatnonzero(remove[row]))
                earned[row] = scores[row,groups.index(group)]
            total_score[rows] += earned
            h[rows] -= ~is_discard
            d[rows] -= is_discard
            used_h[rows] += ~is_discard
            used_d[rows] += is_discard
            green[rows] = np.where(is_discard[:,None],np.maximum(0,green[rows]-self.green_loss),
                                    green[rows]+self.green_gain)
            count = np.minimum(remove.sum(axis=1),remaining)
            draws = np.full((len(rows),self.capacity),self.sentinel,int)
            for row,global_row in enumerate(rows):
                picked = permutations[global_row,cursor[global_row]:cursor[global_row]+count[row]]
                draws[row,:len(picked)] = picked+self.capacity
                available[global_row,picked] = False
            cursor[rows] += count
            hands[rows] = self.refill(current,remove,draws)
            first = False
        wins = total_score>=self.target
        p = float(wins.mean())
        # Wilson interval remains nonzero even for 0/1000 or 1000/1000 wins.
        z = 1.96
        center = (p+z*z/(2*n))/(1+z*z/n)
        radius = z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/(1+z*z/n)
        return {'score':float(total_score.mean()),'win_probability':p,
                'expected_hands_to_win':float(used_h[wins].mean()) if wins.any() else None,
                'expected_discards_used':float(used_d.mean()),
                'win_by_hands':[float(np.mean(wins&(used_h<=k))) for k in range(1,self.hands_left+1)],
                'win_interval_95':[max(0.,center-radius),min(1.,center+radius)],
                'win_error_95':radius,'trials':n,
                'standard_error':float(np.std(total_score,ddof=1)/math.sqrt(n)) if n>1 else 0.,
                'p10':float(np.percentile(total_score,10)),'p90':float(np.percentile(total_score,90))}
