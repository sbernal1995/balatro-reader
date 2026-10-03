# Lector y simulador de Balatro

Asistente local para Balatro con lectura en vivo, historial de partida y comparación de jugadas mediante Monte Carlo.

**Para instalarlo en otra PC, seguí [INSTALACION.md](INSTALACION.md).** Incluye instalador y lanzador para Windows. Después de instalar, abrí `Iniciar.cmd` y pulsá **Simular** en el panel http://127.0.0.1:8765.

## Lectura y registro

El lector consulta el estado cada segundo, aunque el navegador esté cerrado. Guarda mano, comodines, consumibles, niveles y usos de las manos y contexto de partida. La ampliación del mod agrega la baraja completa y los contadores internos de consumibles, probabilidades y valores de cada carta; después de actualizar el mod, reiniciar Balatro para cargarlos.

- `registros/actual.json`: última captura con fecha UTC.
- `registros/historial.jsonl`: capturas cuando cambia el estado.
- `registros/recomendacion.json`: último análisis finalizado junto con el estado que lo originó.

La pila de robo se guarda como composición ordenada por identificador. No se usa su orden real de robo. Las identidades de cartas ocultas de la mano no se usan.

## Monte Carlo

El panel compara todas las selecciones de 1 a 5 cartas para jugar y para descartar como primera acción. Para cada opción simula 1000 rondas, desde el estado actual hasta ganar la ciega o agotar las manos. Acumula las fichas de cada jugada, conserva las cartas retenidas, repone cartas sin reemplazo y actualiza manos, descartes y efectos implementados. Permite encadenar todos los descartes disponibles. Las mismas barajas hipotéticas se usan entre opciones para reducir ruido comparativo. La semilla del simulador es fija para reproducibilidad y es independiente de la semilla del juego.

La decisión prioriza la mayor probabilidad estimada de ganar **esta ciega con las manos restantes**. Si dos opciones tienen el mismo porcentaje, elige la que usa menos manos de media entre las victorias; después prioriza usar los descartes disponibles. Si todas fallan, las fichas acumuladas sirven como desempate. El panel muestra el porcentaje acumulado de ganar con una mano, con hasta dos, etc., las manos necesarias de media entre las victorias, fichas acumuladas y un intervalo de Wilson del 95% para el muestreo. Un intervalo individual no corrige el sesgo de seleccionar la mejor entre muchas opciones ni el error de la estrategia aproximada.

Los descartes tienen su costo real dentro de los efectos implementados: Banner pierde fichas al gastar descartes, Mystic Summit se activa al llegar a cero y el Comodín verde pierde `extra.discard_sub` de Mult por descarte, con mínimo cero, y suma `extra.hand_add` antes de cada mano. El simulador conserva por separado los valores de cada copia del Comodín verde y respeta su posición y edición.

Las recomendaciones muestran el valor y el dibujo del palo de cada carta, por ejemplo As ♠ o J ♥. Las posiciones se usan solo internamente para identificar y destacar las cartas. Para jugar, respetar el orden sugerido, que coloca los aumentos de multiplicador antes de sus multiplicaciones.

El cálculo empieza al pulsar **Simular**. El botón lee de nuevo el estado real y permite repetir el cálculo después de la segunda mano, tercera o cualquier descarte. Durante el análisis se muestran resultados parciales: primero las jugadas y luego los descartes ya evaluados, cada uno con 1000 rondas completas. La barra indica opciones completadas, no tiradas dentro de una misma opción. Una mano de ocho cartas puede requerir varios minutos, según los recursos y efectos. Si cambia la mano, las fichas, los comodines o los recursos, se cancela el análisis y se retira la recomendación anterior hasta pulsar Simular de nuevo. La selección visual de cartas no invalida el cálculo. El lector y la interfaz siguen respondiendo mientras se calcula.

### Alcance actual

El horizonte cubre toda la ciega actual, con todas las manos y los descartes restantes. No ejecuta acciones, usa consumibles ni decide compras. Cerrar el panel no detiene el análisis.

La primera acción se compara exhaustivamente. En estados pequeños (hasta siete cartas entre mano y pila de robo y hasta siete recursos), las decisiones posteriores se resuelven mediante expectimax: enumera robos posibles y elige por probabilidad de victoria y manos necesarias. En estados mayores usa una estrategia de continuación aproximada: evalúa las jugadas de la mano visible, propone retener pares, colores o escaleras y compara jugar con un descarte mediante un robo de prueba independiente y una proyección de fichas sobre las manos restantes. Las decisiones posteriores pueden cambiar al robar. Ese robo de prueba nunca consulta el futuro de la baraja de la ronda simulada. Las 1000 rondas estiman la victoria bajo esta estrategia; **no certifican la probabilidad óptima global**. Siempre conviene recalcular después de cada acción real.

Se calculan las 12 categorías de manos, niveles, mejoras Bonus/Mult/Wild/Glass/Steel/Stone/Gold, sellos rojos y ediciones de puntuación. Se consideran cartas debilitadas, acero retenido y orden de los comodines.

Comodines implementados: Joker, Half Joker, Banner, Mystic Summit, Blue Joker, Abstract Joker, Fortune Teller, Bull, Bootstraps, Gros Michel, Cavendish, Green Joker y las familias Jolly/Zany/Mad/Crazy/Droll y Sly/Wily/Clever/Devious/Crafty. Se usan los valores actuales de sus habilidades; los dos comodines de banana pueden desaparecer al finalizar la ronda, fuera del horizonte del cálculo.

Un comodín desconocido, una mejora Lucky, una carta oculta, una ciega jefe activa o la baraja Plasma bloquean la recomendación con el motivo correspondiente. No se omiten estos efectos para mostrar un número aparentemente completo. Un resultado Monte Carlo tiene incertidumbre; al elegir entre muchas opciones, diferencias pequeñas no demuestran que una sea superior.

## Instalación y validación

API base: https://github.com/coder/balatrobot, descargada por el instalador en `.deps/balatrobot`. El mod instalado está en `%AppData%/Balatro/Mods/balatrobot`. La ampliación distribuida está en `integrations/gamestate.lua`; el instalador la copia en `src/lua/utils/gamestate.lua` de la dependencia y del mod. Lovely está en el directorio del juego y Steamodded en la carpeta Mods.

El instalador prepara Python y NumPy en `.venv`. Las pruebas se ejecutan con ese Python: `python -m unittest test_simulator test_reader -v`. Cubren categorías de manos, niveles, mejoras, sellos, cartas retenidas, orden de efectos, acumulación hasta la tercera mano, cadenas de descartes, preferencia por menos manos, pérdida y crecimiento de Mult, límites de recursos, independencia del futuro de robo, muestreo, cancelación y reglas sin implementar.

La vista muestra cartas y alternativas visuales, recursos restantes, número de jugada, avance hacia la ciega y recursos después de la acción propuesta. El botón queda disponible nuevamente al terminar el cálculo o cambiar la mano. Las pruebas incluyen resultados parciales, recálculo manual y recursos de la segunda, tercera y última mano.

## Licencia y dependencias

Código del lector bajo licencia MIT. La ampliación de BalatroBot conserva su licencia original en `integrations/LICENSE-BalatroBot.txt`. Lovely y Steamodded se descargan desde sus proyectos oficiales; no se redistribuyen sus binarios ni el juego.
