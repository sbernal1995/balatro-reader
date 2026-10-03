# Builds y afinidad en la tienda

El panel incluye una biblioteca local de **12 builds del juego base**, investigada el 3 de octubre de 2026. Se carga al abrir el lector y funciona sin consultar webs durante la partida. Las combinaciones se revisaron contra los efectos del motor; no se importaron los cálculos de puntuación de las guías. Las referencias originales están en cada build, tanto en el panel como en [builds.json](builds.json).

Elegí **Detectar con mis comodines** para identificar un núcleo presente, o seleccioná una **build objetivo**. Las piezas que ya tenés aparecen marcadas. Elegir un objetivo guarda tu preferencia en este navegador y señala las cartas de la tienda que pertenecen a ese plan. Esta selección no modifica tu partida ni supone que ya poseés sus piezas. Se puede explorar la biblioteca incluso con Balatro cerrado.

## Biblioteca inicial

| Build | Núcleo | Preparación |
| --- | --- | --- |
| PhotoChad | Photograph + Hanging Chad | Primera carta que puntúa: figura |
| Baron/Mime | Baron + Mime | Reyes conservados en mano; acero y sellos rojos ayudan |
| Wee/Hack | Wee Joker + Hack | Doses que puntúan varias veces |
| Lucky Cat | Lucky Cat + Oops! All 6s | Cartas de la suerte y repeticiones |
| Bloodstone | Bloodstone + Oops! All 6s | Corazones; Smeared admite diamantes |
| Triboulet | Triboulet + Sock and Buskin | Reyes y reinas que puntúan |
| Vampire/Midas | Vampire + Midas Mask | Figuras mejoradas; revisar el orden |
| DNA/Hologram | DNA + Hologram | Primera jugada de una sola carta; crecimiento de la baraja |
| Piedras | Marble Joker + Stone Joker + Hologram | Incorporar y puntuar piedras |
| Valor de venta | Egg + Swashbuckler | Aumentar el valor de los otros comodines |
| Escaleras | Four Fingers + Shortcut | Rangos variados y niveles de escalera |
| Doble par | Spare Trousers + Square Joker | Doble par jugado con cuatro cartas |

Las fuentes incluyen [experiencias de jugadores](https://www.reddit.com/r/balatro/comments/1iaisav/), [DNA/Hologram](https://www.reddit.com/r/balatro/comments/1sb6o27/hologram_dna_synergy/), [probabilidades y dados](https://www.reddit.com/r/balatro/comments/1oad2ow/how_to_properly_use_oops_all_6s/), [Vampire/Midas](https://www.reddit.com/r/balatro/comments/1txtxx7/is_pareidolia_midas_mask_vampire_a_good_joker/), [Egg/Swashbuckler](https://www.reddit.com/r/balatro/comments/1wddr8e/dna_or_swashbuckler/) y la [biblioteca comunitaria japonesa](https://balatro.jp/combo/). Son referencias de combinaciones, con versiones y opiniones distintas; los textos del panel son explicaciones propias.

## Qué significa el porcentaje

**Es un índice heurístico de compatibilidad de 0 a 100.** Su fórmula y umbrales son propios del lector. No está calibrado con partidas ganadas y no representa probabilidad de victoria, aumento porcentual de fichas ni una recomendación definitiva de compra. Para estimar la victoria de una ciega, usá **Simular** cuando esté iniciada.

Para cada carta se buscan combinaciones revisadas que la incluyan y se muestra la de mayor afinidad con el inventario real:

| Componente | Máximo | Criterio |
| --- | ---: | --- |
| Compañeros | 40 | Fracción de las otras piezas centrales ya presentes; cada apoyo aporta 0,35 piezas equivalentes |
| Baraja | 25 | Preparación de la colección completa para la combinación |
| Núcleo presente | 20 | Fracción de las piezas centrales que ya poseés |
| Desarrollo | 15 | Para estrategias con manos asociadas: 60% niveles hasta nivel 10, 40% usos hasta 20; para otras: XMult persistente hasta ×4 |

La preparación de baraja alcanza su máximo con 35% de figuras/reyes/doses, 50% de reyes o reinas/cartas de la suerte, 40% de piedras o 65% de corazones efectivos, según el perfil. Son referencias del índice, no umbrales necesarios para ganar. En escaleras se considera variedad hasta diez rangos, reducida por la fracción de piedras; para doble par, la fracción de cartas cuyo rango tiene otro ejemplar. Las estrategias sin requisito de baraja reciben los 25 puntos de ese componente.

Una pieza de apoyo recibe factor ×0,85. Una pieza que ya poseés recibe ×0,70, excepto Blueprint/Brainstorm, que comprueban que exista una habilidad compatible y suponen que la colocarás para copiarla. Si no hay cartas que activen el perfil, o si Steel Joker no tiene acero, la afinidad tiene un máximo de 30. Las cifras se redondean al entero y se descuentan conflictos detectados, con piso de cero:

- Pareidolia/Ride the Bus: −45.
- Vampire con Lucky Cat, Steel Joker o Glass Joker: −20 por relación detectada.
- Burglar con efectos dependientes de descartes: −30 por relación.
- Green Joker/Ramen con efectos que buscan descartes: −15 por relación.
- La suma de penalizaciones se limita a 70. Una oferta debilitada con perfil recibe cero.

Los motivos y componentes aparecen en cada oferta. El precio, el crédito activo, los espacios, los eternos, el alquiler y las rondas de los perecederos se muestran **aparte**: no cambian la afinidad. Una carta puede encajar bien y requerir vender otra antes de comprarla. No se simula esa sustitución ni se elige una venta.

## Cobertura y límites

Se evalúan comodines y algunos Tarot/planetas vinculados a estas builds. El registro identifica los 150 comodines base, pero la biblioteca no cubre todas sus relaciones posibles. Una carta sin relación revisada muestra **—**, no 0%; podría ser una excelente compra por su fuerza individual o su economía. Tampoco se atribuye afinidad a contenido desconocido, comodines ocultos o el contenido aleatorio de sobres.

Las cartas ocultas no se identifican por posición. El lector prepara una composición anónima de la colección completa, sin IDs ni orden, para contar correctamente cartas que están boca abajo en el mazo. Si falta esa colección, un perfil que necesita composición queda sin porcentaje. La pila de robo no se usa como sustituto de la baraja completa. Los comodines debilitados no se cuentan como compañeros activos. Los porcentajes no incorporan el efecto completo de ciegas jefe, orden actual, todos los contadores, todas las ediciones, ni el horizonte económico de varias rondas. El simulador conserva sus reglas y su búsqueda independiente; no toma decisiones basadas en este índice.

La biblioteca está en `builds.json`; ampliar una build requiere revisar sus reglas y fuentes y añadir un perfil compatible en `synergies.py` si necesita nuevos criterios. No se descarga ni ejecuta código de una guía, ni se convierte automáticamente cualquier enlace en una build. Los metadatos de `joker_catalog.json` proceden del registro MIT del motor vendorizado; ver [atribución](engine/UPSTREAM.md) y [licencia](engine/vendor/balatro-core/LICENSE).

## Consulta local

- `GET /builds`: biblioteca y metadatos; disponible sin el juego.
- `GET /synergies?build=auto`: afinidad de las ofertas de la tienda actual.
- `GET /synergies?build=baron-mime`: misma afinidad real, marcando esa build objetivo.

La consulta usa el estado ya leído; no compra, vende, juega ni descarta. Se actualiza aproximadamente cada segundo y retira las ofertas al salir de la tienda o perder conexión.
