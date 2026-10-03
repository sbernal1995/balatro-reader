# Reglas del juego base

Este catálogo permite comprobar qué contenido está registrado. Los nombres originales facilitan relacionarlos con las claves de la API; la interfaz conserva los nombres y descripciones localizados que envía el juego.

Las habilidades se ejecutan en el motor, además de estar registradas. La recomendación usa el estado actual y simula sus cambios durante la ciega. La búsqueda de acciones y continuaciones es aproximada, como se explica en [README.md](README.md).

## Dónde se ejecutan

| Contenido | Implementación |
| --- | --- |
| Comodines, copias y fases de efecto | [jokers/effects.rs](engine/vendor/balatro-core/src/jokers/effects.rs), [jokers/mod.rs](engine/vendor/balatro-core/src/jokers/mod.rs) |
| Ciegas y restricciones | [blinds.rs](engine/vendor/balatro-core/src/blinds.rs), [run.rs](engine/vendor/balatro-core/src/run.rs) |
| Mejoras, ediciones, sellos, repeticiones y cartas retenidas | [scoring.rs](engine/vendor/balatro-core/src/scoring.rs), [run.rs](engine/vendor/balatro-core/src/run.rs) |
| Tarot, planetas y espectrales | [tarots.rs](engine/vendor/balatro-core/src/tarots.rs) |
| Ventas, creación y efectos económicos | [shop.rs](engine/vendor/balatro-core/src/shop.rs), [run.rs](engine/vendor/balatro-core/src/run.rs) |
| Contadores, niveles y valores actuales | [import.rs](engine/src/import.rs) |
| Monte Carlo y elección de acciones | [search.rs](engine/src/search.rs) |

## Cartas de juego

Valores 2–10, J, Q, K y As en corazones, diamantes, tréboles y picas. Las mejoras son Bonus, Mult, Wild, Glass, Steel, Stone, Gold y Lucky. Las ediciones son Foil, Holográfica, Policromada y Negativa en las áreas correspondientes. Los sellos son rojo, azul, morado y dorado. Se incluyen bonos permanentes, debilidades, cartas ya jugadas en el ante y selección obligatoria.

## 150 comodines

| Nombre | Clave |
| --- | --- |
| Joker | `j_joker` |
| Greedy Joker | `j_greedy_joker` |
| Lusty Joker | `j_lusty_joker` |
| Wrathful Joker | `j_wrathful_joker` |
| Gluttonous Joker | `j_gluttenous_joker` |
| Jolly Joker | `j_jolly` |
| Zany Joker | `j_zany` |
| Mad Joker | `j_mad` |
| Crazy Joker | `j_crazy` |
| Droll Joker | `j_droll` |
| Sly Joker | `j_sly` |
| Wily Joker | `j_wily` |
| Clever Joker | `j_clever` |
| Devious Joker | `j_devious` |
| Crafty Joker | `j_crafty` |
| Half Joker | `j_half` |
| Joker Stencil | `j_stencil` |
| Four Fingers | `j_four_fingers` |
| Mime | `j_mime` |
| Credit Card | `j_credit_card` |
| Ceremonial Dagger | `j_ceremonial` |
| Banner | `j_banner` |
| Mystic Summit | `j_mystic_summit` |
| Marble Joker | `j_marble` |
| Loyalty Card | `j_loyalty_card` |
| 8 Ball | `j_8_ball` |
| Misprint | `j_misprint` |
| Dusk | `j_dusk` |
| Raised Fist | `j_raised_fist` |
| Chaos the Clown | `j_chaos` |
| Fibonacci | `j_fibonacci` |
| Steel Joker | `j_steel_joker` |
| Scary Face | `j_scary_face` |
| Abstract Joker | `j_abstract` |
| Delayed Gratification | `j_delayed_grat` |
| Hack | `j_hack` |
| Pareidolia | `j_pareidolia` |
| Gros Michel | `j_gros_michel` |
| Even Steven | `j_even_steven` |
| Odd Todd | `j_odd_todd` |
| Scholar | `j_scholar` |
| Business Card | `j_business` |
| Supernova | `j_supernova` |
| Ride the Bus | `j_ride_the_bus` |
| Space Joker | `j_space` |
| Egg | `j_egg` |
| Burglar | `j_burglar` |
| Blackboard | `j_blackboard` |
| Runner | `j_runner` |
| Ice Cream | `j_ice_cream` |
| DNA | `j_dna` |
| Splash | `j_splash` |
| Blue Joker | `j_blue_joker` |
| Sixth Sense | `j_sixth_sense` |
| Constellation | `j_constellation` |
| Hiker | `j_hiker` |
| Faceless Joker | `j_faceless` |
| Green Joker | `j_green_joker` |
| Superposition | `j_superposition` |
| To Do List | `j_todo_list` |
| Cavendish | `j_cavendish` |
| Card Sharp | `j_card_sharp` |
| Red Card | `j_red_card` |
| Madness | `j_madness` |
| Square Joker | `j_square` |
| Seance | `j_seance` |
| Riff-raff | `j_riff_raff` |
| Vampire | `j_vampire` |
| Shortcut | `j_shortcut` |
| Hologram | `j_hologram` |
| Vagabond | `j_vagabond` |
| Baron | `j_baron` |
| Cloud 9 | `j_cloud_9` |
| Rocket | `j_rocket` |
| Obelisk | `j_obelisk` |
| Midas Mask | `j_midas_mask` |
| Luchador | `j_luchador` |
| Photograph | `j_photograph` |
| Gift Card | `j_gift` |
| Turtle Bean | `j_turtle_bean` |
| Erosion | `j_erosion` |
| Reserved Parking | `j_reserved_parking` |
| Mail-In Rebate | `j_mail` |
| To the Moon | `j_to_the_moon` |
| Hallucination | `j_hallucination` |
| Fortune Teller | `j_fortune_teller` |
| Juggler | `j_juggler` |
| Drunkard | `j_drunkard` |
| Stone Joker | `j_stone` |
| Golden Joker | `j_golden` |
| Lucky Cat | `j_lucky_cat` |
| Baseball Card | `j_baseball` |
| Bull | `j_bull` |
| Diet Cola | `j_diet_cola` |
| Trading Card | `j_trading` |
| Flash Card | `j_flash` |
| Popcorn | `j_popcorn` |
| Spare Trousers | `j_trousers` |
| Ancient Joker | `j_ancient` |
| Ramen | `j_ramen` |
| Walkie Talkie | `j_walkie_talkie` |
| Seltzer | `j_selzer` |
| Castle | `j_castle` |
| Smiley Face | `j_smiley` |
| Campfire | `j_campfire` |
| Golden Ticket | `j_ticket` |
| Mr. Bones | `j_mr_bones` |
| Acrobat | `j_acrobat` |
| Sock and Buskin | `j_sock_and_buskin` |
| Swashbuckler | `j_swashbuckler` |
| Troubadour | `j_troubadour` |
| Certificate | `j_certificate` |
| Smeared Joker | `j_smeared` |
| Throwback | `j_throwback` |
| Hanging Chad | `j_hanging_chad` |
| Rough Gem | `j_rough_gem` |
| Bloodstone | `j_bloodstone` |
| Arrowhead | `j_arrowhead` |
| Onyx Agate | `j_onyx_agate` |
| Glass Joker | `j_glass` |
| Showman | `j_ring_master` |
| Flower Pot | `j_flower_pot` |
| Blueprint | `j_blueprint` |
| Wee Joker | `j_wee` |
| Merry Andy | `j_merry_andy` |
| Oops! All 6s | `j_oops` |
| The Idol | `j_idol` |
| Seeing Double | `j_seeing_double` |
| Matador | `j_matador` |
| Hit the Road | `j_hit_the_road` |
| The Duo | `j_duo` |
| The Trio | `j_trio` |
| The Family | `j_family` |
| The Order | `j_order` |
| The Tribe | `j_tribe` |
| Stuntman | `j_stuntman` |
| Invisible Joker | `j_invisible` |
| Brainstorm | `j_brainstorm` |
| Satellite | `j_satellite` |
| Shoot the Moon | `j_shoot_the_moon` |
| Driver's License | `j_drivers_license` |
| Cartomancer | `j_cartomancer` |
| Astronomer | `j_astronomer` |
| Burnt Joker | `j_burnt` |
| Bootstraps | `j_bootstraps` |
| Caino | `j_caino` |
| Triboulet | `j_triboulet` |
| Yorick | `j_yorick` |
| Chicot | `j_chicot` |
| Perkeo | `j_perkeo` |

## 28 ciegas jefe

| Nombre | Clave |
| --- | --- |
| The Ox | `bl_ox` |
| The Hook | `bl_hook` |
| The Mouth | `bl_mouth` |
| The Fish | `bl_fish` |
| The Club | `bl_club` |
| The Manacle | `bl_manacle` |
| The Tooth | `bl_tooth` |
| The Wall | `bl_wall` |
| The House | `bl_house` |
| The Mark | `bl_mark` |
| Cerulean Bell | `bl_final_bell` |
| The Wheel | `bl_wheel` |
| The Arm | `bl_arm` |
| The Psychic | `bl_psychic` |
| The Goad | `bl_goad` |
| The Water | `bl_water` |
| The Eye | `bl_eye` |
| The Plant | `bl_plant` |
| The Needle | `bl_needle` |
| The Head | `bl_head` |
| Verdant Leaf | `bl_final_leaf` |
| Violet Vessel | `bl_final_vessel` |
| The Window | `bl_window` |
| The Serpent | `bl_serpent` |
| The Pillar | `bl_pillar` |
| The Flint | `bl_flint` |
| Amber Acorn | `bl_final_acorn` |
| Crimson Heart | `bl_final_heart` |

## 52 consumibles

| Nombre | Clave |
| --- | --- |
| The Fool | `c_fool` |
| The Magician | `c_magician` |
| The High Priestess | `c_high_priestess` |
| The Empress | `c_empress` |
| The Emperor | `c_emperor` |
| The Hierophant | `c_heirophant` |
| The Lovers | `c_lovers` |
| The Chariot | `c_chariot` |
| Justice | `c_justice` |
| The Hermit | `c_hermit` |
| The Wheel of Fortune | `c_wheel_of_fortune` |
| Strength | `c_strength` |
| The Hanged Man | `c_hanged_man` |
| Death | `c_death` |
| Temperance | `c_temperance` |
| The Devil | `c_devil` |
| The Tower | `c_tower` |
| The Star | `c_star` |
| The Moon | `c_moon` |
| The Sun | `c_sun` |
| Judgement | `c_judgement` |
| The World | `c_world` |
| Mercury | `c_mercury` |
| Venus | `c_venus` |
| Earth | `c_earth` |
| Mars | `c_mars` |
| Jupiter | `c_jupiter` |
| Saturn | `c_saturn` |
| Uranus | `c_uranus` |
| Neptune | `c_neptune` |
| Pluto | `c_pluto` |
| Planet X | `c_planet_x` |
| Ceres | `c_ceres` |
| Eris | `c_eris` |
| Familiar | `c_familiar` |
| Grim | `c_grim` |
| Incantation | `c_incantation` |
| Talisman | `c_talisman` |
| Aura | `c_aura` |
| Wraith | `c_wraith` |
| Sigil | `c_sigil` |
| Ouija | `c_ouija` |
| Ectoplasm | `c_ectoplasm` |
| Immolate | `c_immolate` |
| Ankh | `c_ankh` |
| Deja Vu | `c_deja_vu` |
| Hex | `c_hex` |
| Trance | `c_trance` |
| Medium | `c_medium` |
| Cryptid | `c_cryptid` |
| The Soul | `c_soul` |
| Black Hole | `c_black_hole` |
